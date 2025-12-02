"""Utility helpers to detect disulfide bridges in PDB structures."""
from __future__ import annotations

from typing import Iterable, List, Tuple

from Bio.PDB import PDBParser

DEFAULT_SSBOND_DISTANCE = 2.2  # Ångstroms


def _collect_cys_sg_atoms(structure) -> List[Tuple[int, object]]:
    """Extract all CYS residues that have an SG atom."""
    cys_sg_atoms: List[Tuple[int, object]] = []
    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.get_resname() == "CYS":
                    sg_atom = residue.child_dict.get("SG")
                    if sg_atom is not None:
                        cys_sg_atoms.append((residue.get_id()[1], sg_atom))
    return cys_sg_atoms


def find_disulfide_pairs(structure, max_distance: float = DEFAULT_SSBOND_DISTANCE) -> List[Tuple[int, int]]:
    """Return residue-index pairs that form disulfide bridges."""
    cys_sg_atoms = _collect_cys_sg_atoms(structure)
    if len(cys_sg_atoms) < 2:
        return []

    bridges: List[Tuple[int, int]] = []
    for i, (res_i, atom_i) in enumerate(cys_sg_atoms):
        for j in range(i + 1, len(cys_sg_atoms)):
            res_j, atom_j = cys_sg_atoms[j]
            if (atom_i - atom_j) < max_distance:
                bridges.append((res_i, res_j))
    return bridges


def count_disulfide_bridges_from_structure(structure, max_distance: float = DEFAULT_SSBOND_DISTANCE) -> int:
    """Return the number of disulfide bridges present in the given structure."""
    return len(find_disulfide_pairs(structure, max_distance))


def count_disulfide_bridges_from_pdb(pdb_path: str, max_distance: float = DEFAULT_SSBOND_DISTANCE) -> int:
    """Parse a PDB file and count disulfide bridges."""
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("prot", pdb_path)
    return count_disulfide_bridges_from_structure(structure, max_distance)
