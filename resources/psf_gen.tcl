# Requisitos: ejecutar dentro de VMD (para atomselect/measure) y tener psfgen disponible.
# Uso mínimo:
#   set out [build_psf_with_disulfides input.pdb {top_all36_prot.rtf} output_prefix PROA 2.3]
#   puts "PSF: [lindex $out 0]"
#   puts "PDB: [lindex $out 1]"

package require psfgen

# --------- Utilidad: emparejar por distancia mínima sin reutilizar residuos ---------
proc _greedy_pair_by_distance {pairs_with_d} {
    # pairs_with_d: lista de elementos {resid1 resid2 dist}
    # Devuelve lista de pares únicos {resid1 resid2}
    # Estrategia: ordena por distancia creciente y empareja sin reutilizar resids
    set used {}
    set result {}
    # Ordenar por la columna 2 (distancia)
    set sorted [lsort -real -index 2 $pairs_with_d]
    foreach triple $sorted {
        lassign $triple r1 r2 d
        if { [lsearch -exact $used $r1] >= 0 || [lsearch -exact $used $r2] >= 0 } {
            continue
        }
        lappend used $r1 $r2
        lappend result [list $r1 $r2]
    }
    return $result
}

# --------- Calcula distancia entre dos puntos 3D ---------
proc _calculate_distance {coord1 coord2} {
    set dx [expr {[lindex $coord1 0] - [lindex $coord2 0]}]
    set dy [expr {[lindex $coord1 1] - [lindex $coord2 1]}]
    set dz [expr {[lindex $coord1 2] - [lindex $coord2 2]}]
    return [expr {sqrt($dx*$dx + $dy*$dy + $dz*$dz)}]
}

# --------- Detecta pares CYS–CYS candidatos a DISU por distancia SG–SG ---------
proc find_ssbonds {pdb_path {cutoff 2.3}} {
    # Abre PDB, mide distancias entre SG de CYS, propone pares
    # Retorna lista de pares { {segid1 resid1} {segid2 resid2} } si el PDB tiene segid por columna,
    # de lo contrario retorna { {resid1} {resid2} } y se asumirá un único segid luego.
    
    # Verificar si hay una molécula cargada y limpiar
    set nmols [molinfo num]
    for {set i 0} {$i < $nmols} {incr i} {
        mol delete $i
    }
    
    set molid [mol new $pdb_path type pdb waitfor all]
    if {$molid == -1} {
        error "No se pudo cargar el archivo PDB: $pdb_path"
    }
    
    set sel [atomselect $molid "name SG and resname CYS"]
    set num_sg [$sel num]
    
    if {$num_sg == 0} {
        puts "No se encontraron átomos SG de cisteína"
        $sel delete
        mol delete $molid
        return {}
    }
    
    puts "Encontrados $num_sg átomos SG de cisteína"
    
    # Extrae resids, segids y coords
    set resids [$sel get resid]
    set segids {}
    # Si el PDB trae segid, VMD lo mapea a "segid" (si no, será cadena vacía)
    set segid_list [$sel get segid]
    if { [llength $segid_list] > 0 && [lindex $segid_list 0] ne "" } {
        set segids $segid_list
    } else {
        # rellena con vacío; el caller podrá definir un segid global
        foreach r $resids { lappend segids "" }
    }
    set coords [$sel get {x y z}]
    $sel delete

    set n [llength $resids]
    set candidates {}
    
    puts "Calculando distancias entre $n átomos SG..."
    
    for {set i 0} {$i < $n} {incr i} {
        set ri   [lindex $resids $i]
        set segi [lindex $segids $i]
        set ci   [lindex $coords $i]
        for {set j [expr {$i+1}]} {$j < $n} {incr j} {
            set rj   [lindex $resids $j]
            set segj [lindex $segids $j]
            set cj   [lindex $coords $j]
            
            # Usar nuestra función de distancia personalizada
            set d [_calculate_distance $ci $cj]
            
            puts "Distancia SG $ri - SG $rj: $d Å"
            
            if { $d <= $cutoff } {
                puts "  -> Candidato a enlace disulfuro (distancia: $d Å)"
                # Guardamos triple para emparejamiento posterior
                # Mantén también los segids por si hay múltiples segmentos
                lappend candidates [list [list $segi $ri] [list $segj $rj] $d]
            }
        }
    }

    mol delete $molid

    if {[llength $candidates] == 0} {
        puts "No se encontraron candidatos a enlaces disulfuro dentro del cutoff de $cutoff Å"
        return {}
    }

    # Convertir a pares no solapados (greedy por distancia)
    # Primero a formato {resid1 resid2 dist} ignorando segid para el emparejamiento,
    # pero conservaremos segid cuando exista
    set flat {}
    foreach cand $candidates {
        lassign $cand a b d
        # a = {segid resid}, b = {segid resid}
        set ra [lindex $a 1]
        set rb [lindex $b 1]
        lappend flat [list $ra $rb $d]
    }

    set chosen [_greedy_pair_by_distance $flat]

    # Reconstruir con segid si lo teníamos
    set results {}
    foreach pair $chosen {
        lassign $pair ra rb
        # buscar segids correspondientes (primera coincidencia en candidates)
        set sega ""
        set segb ""
        foreach cand $candidates {
            lassign $cand a b d
            if { ([lindex $a 1] == $ra && [lindex $b 1] == $rb) ||
                 ([lindex $a 1] == $rb && [lindex $b 1] == $ra) } {
                set sega [lindex $a 0]
                set segb [lindex $b 0]
                break
            }
        }
        lappend results [list [list $sega $ra] [list $segb $rb]]
    }
    
    puts "Enlaces disulfuro seleccionados: [llength $results]"
    return $results
}

# --------- Sanea PDB: elimina caps/residuos no estándar y renumera resid, forzando un segid único
proc _sanitize_pdb_for_psfgen {in_pdb segid} {
    set bad {NH2 PCA NME ACE}
    set molid [mol new $in_pdb type pdb waitfor all]
    if {$molid == -1} { error "No se pudo cargar PDB para sanitizar: $in_pdb" }
    set sel [atomselect $molid "not (resname [join $bad { or resname }])"]
    if { [$sel num] == 0 } {
        $sel delete
        mol delete $molid
        error "PDB vacío tras sanitizar (todos los residuos eran no estándar)"
    }
    # Renumerar resid por índice de residuo único de VMD
    set residue_idx [$sel get residue]
    set uniq [lsort -unique $residue_idx]
    array unset map
    set rid 1
    foreach r $uniq { set map($r) $rid; incr rid }
    set newresids {}
    foreach r $residue_idx { lappend newresids $map($r) }
    $sel set resid $newresids
    $sel set segid $segid
    $sel set segname $segid
    set tmp [file join [file dirname $in_pdb] "psfgen_sanitized_[pid]_[clock clicks].pdb"]
    $sel writepdb $tmp
    $sel delete
    mol delete $molid
    return $tmp
}

proc build_psf_with_disulfides {in_pdb topologies out_prefix {segid PROA} {ss_cutoff 2.3}} {
    puts "Iniciando construcción PSF para: $in_pdb"
    puts "Topologías: $topologies"
    puts "Prefijo salida: $out_prefix"
    puts "Segmento: $segid"
    puts "Cutoff disulfuro: $ss_cutoff Å"

    resetpsf

    if {![info exists ::PSFGEN_TOP_LOADED]} {
        foreach top $topologies {
            puts "Cargando topología: $top"
            topology $top
        }
        set ::PSFGEN_TOP_LOADED 1
    } else {
        puts "Topologías ya cargadas previamente; no se recargarán."
    }

    if {![info exists ::PSFGEN_ALIASES_SET]} {
        pdbalias atom ILE CD1 CD
        pdbalias residue HIS HSE
        pdbalias residue HID HSD
        pdbalias residue HIE HSE
        pdbalias residue HIP HSP
        pdbalias residue HSD HSD
        pdbalias residue HSE HSE
        pdbalias residue HSP HSP
        pdbalias residue MSE MET
        pdbalias residue SEC CYS
        pdbalias residue CYX CYS
        set ::PSFGEN_ALIASES_SET 1
    }

    # 1) Saneado PDB
    set san_pdb [_sanitize_pdb_for_psfgen $in_pdb $segid]

    # 2) Segmento y coords con el PDB saneado
    puts "Construyendo segmento $segid..."
    if {[catch { segment $segid { pdb $san_pdb } } segerr]} {
        error "ERROR al crear segmento: $segerr"
    }
    coordpdb $san_pdb $segid

    # 3) DISU sobre el PDB saneado
    puts "Buscando enlaces disulfuro..."
    set ss_pairs [find_ssbonds $san_pdb $ss_cutoff]

    set patch_count 0
    foreach pair $ss_pairs {
        lassign $pair a b
        # Forzar segmento único y resid enteros
        set resa [lindex $a 1]; if {![string is integer -strict $resa]} { catch { set resa [expr {int($resa)}] } }
        set resb [lindex $b 1]; if {![string is integer -strict $resb]} { catch { set resb [expr {int($resb)}] } }
        puts ">> Aplicando patch DISU entre $segid:$resa y $segid:$resb"
        if {[catch {patch DISU $segid:$resa $segid:$resb} perr]} {
            puts "Error aplicando patch DISU: $perr"
        } else { incr patch_count }
    }
    puts "Total de patches DISU aplicados: $patch_count"

    regenerate angles dihedrals
    guesscoord

    set psf "${out_prefix}.psf"
    set pdb "${out_prefix}.pdb"
    writepsf $psf
    writepdb $pdb

    catch { file delete -force $san_pdb }

    return [list $psf $pdb]
}
