import json
import os
import re
from collections.abc import Callable
from typing import Any, List

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# ---------------------------------------------------------------------------
# Configuración del cliente vLLM
# ---------------------------------------------------------------------------
# Global cache para evitar reinicialización
_client_cache = None
_model_name_cache = None

def get_ai_client():
    """Inicializa el cliente IA solo cuando se necesita (lazy loading)."""
    global _client_cache, _model_name_cache
    if _client_cache is None:
        base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        _client_cache = OpenAI(base_url=base_url, api_key=os.getenv("VLLM_API_KEY"))
        _model_name_cache = os.getenv("VLLM_MODEL")
        print("Client initialized", _client_cache)
        print("Model:", _model_name_cache)
    return _client_cache, _model_name_cache

# ---------------------------------------------------------------------------
# FEW-SHOT EXAMPLES - Con casos de rangos y orden de potencia
# ---------------------------------------------------------------------------
few_shot_examples = [
    # Ejemplo 1: Texto simple con IC50
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "The compound exhibited potent Nav1.7 inhibition with an IC50 of 25 nM in patch-clamp assays."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [],
  "ic50_values": [
    {
      "value": 25,
      "unit": "nM",
      "context": "The compound exhibited potent Nav1.7 inhibition with an IC50 of 25 nM in patch-clamp assays.",
      "type": "exact"
    }
  ],
  "summary": "Se encontró 1 valor exacto de IC50 (25 nM) para Nav1.7."
}"""
    },
    
    # Ejemplo 2: Rango con orden de potencia (CASO CLAVE)
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "The relative rank order potency for Nav modulation is Nav1.3 (inactivation EC50=45 nM) > Nav1.7 > Nav1.2 > Nav1.1 (inactivation) > Nav1.1 > Nav1.6 > Nav1.3 (IC50=8 uM)."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [],
  "ic50_values": [
    {
      "value_min": 45,
      "value_max": 8000,
      "unit_min": "nM",
      "unit_max": "nM",
      "context": "The relative rank order potency for Nav modulation is Nav1.3 (inactivation EC50=45 nM) > Nav1.7 > Nav1.2 > Nav1.1 (inactivation) > Nav1.1 > Nav1.6 > Nav1.3 (IC50=8 uM).",
      "type": "range",
      "interpretation": "Nav1.7 está en un rango de potencia entre 45 nM (Nav1.3, más potente) y 8000 nM (8 µM, Nav1.3 con IC50, menos potente). El símbolo > indica que Nav1.7 es menos potente que Nav1.3 (45 nM) pero más potente que los canales posteriores en la serie."
    }
  ],
  "summary": "Nav1.7 aparece en un ranking de potencia. Se infiere que el IC50 está en el rango de >45 nM a <8000 nM (8 µM) basado en el orden relativo de potencia."
}"""
    },
    
    # Ejemplo 3: Rango explícito con "between"
    {
        "role": "user",        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "The IC50 for Nav1.7 was between 50 nM and 200 nM, showing moderate selectivity over Nav1.5."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [],
  "ic50_values": [
    {
      "value_min": 50,
      "value_max": 200,
      "unit_min": "nM",
      "unit_max": "nM",
      "context": "The IC50 for Nav1.7 was between 50 nM and 200 nM, showing moderate selectivity over Nav1.5.",
      "type": "range",
      "interpretation": "El IC50 para Nav1.7 está explícitamente en el rango de 50 a 200 nM."
    }
  ],
  "summary": "Se encontró un rango de IC50 para Nav1.7: 50-200 nM."
}"""
    },
    
    # Ejemplo 4: Mayor que (>)
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "The compound showed IC50 > 10 µM for Nav1.7, indicating weak activity."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [],
  "ic50_values": [
    {
      "value_min": 10000,
      "value_max": null,
      "unit_min": "nM",
      "unit_max": null,
      "context": "The compound showed IC50 > 10 µM for Nav1.7, indicating weak activity.",
      "type": "greater_than",
      "interpretation": "El IC50 es mayor que 10 µM (10000 nM), lo que indica actividad débil o ausencia de actividad significativa."
    }
  ],
  "summary": "IC50 >10 µM (>10000 nM) para Nav1.7, indicando poca o nula actividad."
}"""
    },
    
    # Ejemplo 5: Menor que (<)
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "Nav1.7 inhibition was observed with IC50 < 100 nM, demonstrating high potency."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [],
  "ic50_values": [
    {
      "value_min": null,
      "value_max": 100,
      "unit_min": null,
      "unit_max": "nM",
      "context": "Nav1.7 inhibition was observed with IC50 < 100 nM, demonstrating high potency.",
      "type": "less_than",
      "interpretation": "El IC50 es menor que 100 nM, indicando alta potencia."
    }
  ],
  "summary": "IC50 <100 nM para Nav1.7, demostrando alta potencia."
}"""
    },
    
    # Ejemplo 6: Aproximadamente (~)
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "The Kd for Nav1.7 binding was approximately 35 nM (Kd ~ 35 nM)."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [
    {
      "value": 35,
      "unit": "nM",
      "context": "The Kd for Nav1.7 binding was approximately 35 nM (Kd ~ 35 nM).",
      "type": "approximate",
      "interpretation": "El valor es aproximado (~35 nM), no es una medición exacta."
    }
  ],
  "ic50_values": [],
  "summary": "Se encontró 1 valor aproximado de Kd (~35 nM) para Nav1.7."
}"""
    },
    
    # Ejemplo 7: Múltiples valores con rangos
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "Compound A: Nav1.7 IC50 = 12.5 nM, Kd = 8.3 nM. Compound B: Nav1.7 IC50 between 50-150 nM. Compound C: Nav1.7 IC50 > 5 µM."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [
    {
      "value": 8.3,
      "unit": "nM",
      "context": "Compound A: Nav1.7 IC50 = 12.5 nM, Kd = 8.3 nM",
      "type": "exact",
      "compound": "Compound A"
    }
  ],
  "ic50_values": [
    {
      "value": 12.5,
      "unit": "nM",
      "context": "Compound A: Nav1.7 IC50 = 12.5 nM, Kd = 8.3 nM",
      "type": "exact",
      "compound": "Compound A"
    },
    {
      "value_min": 50,
      "value_max": 150,
      "unit_min": "nM",
      "unit_max": "nM",
      "context": "Compound B: Nav1.7 IC50 between 50-150 nM",
      "type": "range",
      "compound": "Compound B",
      "interpretation": "IC50 en rango de 50 a 150 nM"
    },
    {
      "value_min": 5000,
      "value_max": null,
      "unit_min": "nM",
      "unit_max": null,
      "context": "Compound C: Nav1.7 IC50 > 5 µM",
      "type": "greater_than",
      "compound": "Compound C",
      "interpretation": "IC50 mayor que 5 µM (5000 nM), actividad muy débil"
    }
  ],
  "summary": "Se encontraron 3 valores de IC50 y 1 valor de Kd para Nav1.7 en 3 compuestos diferentes. Compound A es el más potente (IC50=12.5 nM), seguido de Compound B (IC50=50-150 nM), y Compound C muestra actividad débil (IC50 >5 µM)."
}"""
    },
    
    # Ejemplo 8: Sin valores para Nav1.7
    {
        "role": "user",
        "content": """Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "The compound showed moderate activity against Nav1.5 with IC50 of 120 nM. No significant activity was observed against Nav1.7."

Responde en formato JSON."""
    },
    {
        "role": "assistant",
        "content": """{
  "target": "Nav1.7",
  "kd_values": [],
  "ic50_values": [],
  "summary": "No se encontraron valores cuantitativos de Kd ni IC50 para Nav1.7. El texto menciona ausencia de actividad significativa contra Nav1.7."
}"""
    },
]


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Eres un experto en análisis de literatura científica farmacológica especializado en canales de sodio. Tu tarea es extraer valores de Kd (constante de disociación) e IC50 (concentración inhibitoria media) específicamente para Nav1.7 (también conocido como SCN9A).

INSTRUCCIONES PARA EXTRACCIÓN:

1. **Targets**: Busca menciones de Nav1.7, Nav 1.7, NaV1.7, SCN9A, o "sodium channel type 9"

2. **Tipos de valores a extraer**:
   a) **Valores exactos**: "IC50 = 25 nM", "Kd of 12.5 nM"
   b) **Valores aproximados**: "IC50 ~ 30 nM", "approximately 45 nM"
   c) **Rangos explícitos**: "IC50 between 50-200 nM", "IC50 from 10 to 100 nM"
   d) **Mayor que**: "IC50 > 10 µM", "Kd > 500 nM"
   e) **Menor que**: "IC50 < 100 nM", "Kd < 50 nM"
   f) **Rangos inferidos de orden de potencia**: 
      - Si ves "Nav1.3 (IC50=45 nM) > Nav1.7 > ... > Nav1.8 (IC50=8 µM)"
      - Interpreta que Nav1.7 está ENTRE 45 nM y 8 µM
      - El símbolo ">" indica orden de potencia (mayor potencia = menor IC50)

3. **Unidades**: Normaliza a nM cuando sea posible
   - pM → divide por 1000
   - µM → multiplica por 1000
   - mM → multiplica por 1,000,000

4. **Contexto**: Incluye la oración completa donde aparece el valor

5. **Interpretación**: Para rangos y valores relacionales, explica el significado

6. **Ignorar**: Valores para otros canales (Nav1.5, Nav1.8, etc.) a menos que ayuden a establecer un rango para Nav1.7

FORMATO DE RESPUESTA JSON:

Para valores EXACTOS o APROXIMADOS:
{
  "value": número,
  "unit": "nM" | "µM" | "pM",
  "context": "oración completa",
  "type": "exact" | "approximate",
  "compound": "nombre del compuesto (si aplica)"
}

Para RANGOS o comparaciones:
{
  "value_min": número o null,
  "value_max": número o null,
  "unit_min": "nM" | "µM" | null,
  "unit_max": "nM" | "µM" | null,
  "context": "oración completa",
  "type": "range" | "greater_than" | "less_than",
  "interpretation": "explicación del rango o comparación",
  "compound": "nombre del compuesto (si aplica)"
}

ESTRUCTURA COMPLETA:
{
  "target": "Nav1.7" o "SCN9A" o "Nav1.7/SCN9A",
  "kd_values": [ ... array de valores ... ],
  "ic50_values": [ ... array de valores ... ],
  "summary": "Resumen conciso de los hallazgos"
}

IMPORTANTE: RESPONDE ÚNICAMENTE con el JSON solicitado. No incluyas explicaciones ni razonamientos ni etiquetas como <think>. Si por algún motivo incluyes texto adicional, encierra el JSON final en un bloque de código marcado con ```json ... ```."""


# ---------------------------------------------------------------------------
# Función para crear mensajes
# ---------------------------------------------------------------------------
def create_few_shot_messages(user_text: str) -> List[dict]:
    """Crea el array de mensajes con few-shot examples."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(few_shot_examples)
    messages.append({
        "role": "user",
        "content": f"""Analiza este texto y extrae valores de Kd e IC50 para Nav1.7/SCN9A:

Texto: "{user_text}"

Responde en formato JSON."""
    })
    return messages


# ---------------------------------------------------------------------------
# Función principal de análisis
# ---------------------------------------------------------------------------
def analyze_text_for_nav17(text: str, verbose: bool = True) -> dict:
    """Analiza un texto usando el modelo con few-shot learning."""
    client, MODEL_NAME = get_ai_client()  # ← Obtener aquí
    messages = create_few_shot_messages(text)
    
    if verbose:
        print("=" * 80)
        print("ANÁLISIS CON FEW-SHOT LEARNING (con soporte para rangos)")
        print("=" * 80)
        print(f"\nTexto a analizar:\n{text}\n")
        print("=" * 80)
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.0,
            max_tokens=2048,
        )
        
        assistant_msg = response.choices[0].message
        raw = assistant_msg.content if hasattr(assistant_msg, "content") else str(assistant_msg)
        
        # --- Robust JSON extraction ---
        def try_extract_json(s: str):
            s = s.strip()
            # 1) direct parse
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
            # 2) fenced code block ```json ... ```
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            # 3) first '{' .. last '}' (object)
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = s[start:end+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            # 4) first '[' .. last ']' (array)
            start = s.find("[")
            end = s.rfind("]")
            if start != -1 and end != -1 and end > start:
                candidate = s[start:end+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            # nothing worked
            raise json.JSONDecodeError("No JSON found in model response", s, 0)
        
        try:
            result = try_extract_json(raw)
            if verbose:
                print("\n📊 RESPUESTA DEL MODELO (JSON extraído):")
                print("-" * 80)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("-" * 80)
            return result
        except json.JSONDecodeError as e:
            error_result = {
                "error": f"Error parseando JSON: {e}",
                "raw_response": raw
            }
            if verbose:
                print(f"❌ Error: {error_result['error']}")
                print(f"Respuesta raw: {raw}")
            return error_result
    except Exception as e:
        error_result = {"error": f"Error en la llamada al modelo: {str(e)}"}
        if verbose:
            print(f"❌ {error_result['error']}")
        return error_result


# ---------------------------------------------------------------------------
# EJEMPLOS DE USO
# ---------------------------------------------------------------------------
'''
if __name__ == "__main__":
    
    # Ejemplo 1: TU CASO - Orden de potencia con rango
    print("\n" + "🔬 EJEMPLO 1: Orden de potencia (tu caso)" + "\n")
    text1 = """
    This lethal neurotoxin (without cyclization at position 53) inhibits neuronal voltage-gated sodium channel Nav1.2/SCN2A (IC50=10-150 nM), rNav1.3/SCN3A (IC50=338 nM), Nav1.6/SCN8A (IC50=117 nM), and hNav1.7/SCN9A (IC50=9.6-33 nM) (PubMed:18628201, PubMed:20855463, PubMed:23760503, PubMed:25658507, PubMed:29703751, PubMed:31234412).
It inhibits activation of sodium channel by trapping the voltage sensor of domain II (DIIS4) in the closed configuration (PubMed:18628201, PubMed:23760503).
The toxin neither shifts the Nav1.7/SCN9A activation curve nor modifies the slope factor (PubMed:20855463).
It does not slow fast-inactivation of hNav1.7/SCN9A channels (PubMed:20855463).
In addition, it has only a weak affinity for lipid membranes (PubMed:18054060, PubMed:28115115, PubMed:29703751).
This toxin also exists with a pyroglutamate at position 53 (PubMed:23826086).
The sole difference observed between modified (mHwTx-IV) and unmodified toxins is that moderate or high depolarization voltages (200 mV) permit the unmodified toxin to dissociate, whereas mHwTx-IV toxin does not dissociate, even at high depolarization voltages (PubMed:23826086).
These data indicate that mHwTx-IV strongly binds to voltage sensor of sodium channel even at extreme depolarization voltages (PubMed:23826086).
    """
    result1 = analyze_text_for_nav17(text1)
    
    
    # Ejemplo 2: Rangos explícitos
    print("\n" + "🔬 EJEMPLO 2: Rango explícito" + "\n")
    text2 = """
  Selective antagonist of neuronal tetrodotoxin (TTX)-sensitive voltage-gated sodium channels (IC50=1270 nM on Nav1.1/SCN1A, 270 nM on Nav1.2/SCN2A, 491 nM on Nav1.3/SCN3A and 232 nM on Nav1.7/SCN9A). This toxin suppress Nav1.7 current amplitude without significantly altering the activation, inactivation, and repriming kinetics. Short extreme depolarizations partially activate the toxin-bound channel, indicating voltage-dependent inhibition of this toxin. This toxin increases the deactivation of the Nav1.7 current after extreme depolarizations. The toxin-Nav1.7 complex is gradually dissociated upon prolonged strong depolarizations in a voltage-dependent manner, and the unbound toxin rebinds to Nav1.7 after a long repolarization. Moreover, analysis of chimeric channels showed that the DIIS3-S4 linker is critical for toxin binding to Nav1.7. These data are consistent with this toxin interacting with Nav1.7 site 4 and trapping the domain II voltage sensor in the closed state.
    """
    result2 = analyze_text_for_nav17(text2)
    
    
    # Ejemplo 3: Mayor que / Menor que
    print("\n" + "🔬 EJEMPLO 3: Comparaciones" + "\n")
    text3 = """
    Gating-modifier toxin that inhibits both sodium (Nav) and calcium (Cav3) channels by inducing hyperpolarizing shift in voltage-dependence of activation and steady state inactivation. Inhibits Nav1.1/SCN1A, Nav1.2/SCN2A, Nav1.3/SCN3A, Nav1.6/SCN6A, Nav1.7/SCN9A and Cav3.1/CACNA1G sodium and calcium channels at nanomolar concentrations (IC50=81-301 nM). Surprisingly, selectively slows fast inactivation of Nav1.3/SCN3A. Also shows moderate inhibition of Cav3.2/CACNA1H calcium channels (IC50=1233 nM). Ex vivo, nearly ablates neuronal mechanosensitivity in afferent fibers innervating the colon and the bladder. In vivo, in a mouse model of irritable bowel syndrome, intracolonic administration of the toxin reverses colonic mechanical hypersensitivity.
    """
    result3 = analyze_text_for_nav17(text3)


    print("\n" + "texto final" + "\n")
    text4 = """
    Gating-modifier toxin that both inhibits the peak current of human Nav1.1/SCN1A, rat Nav1.2/SCN2A, human Nav1.6/SCN8A, and human Nav1.7/SCN9A and concurrently inhibits fast inactivation of human Nav1.1 and rat Nav1.3/SCN3A. The relative rank order potency for Nav modulation is Nav1.3 (inactivation EC50=45 nM) > Nav1.7 > Nav1.2 > Nav1.1 (inactivation) > Nav1.1 > Nav1.6 > Nav1.3 (IC50=8 uM). The DII and DIV S3-S4 loops of Nav channel voltage sensors are important for the interaction of this toxin with Nav channels but cannot account for its unique subtype selectivity. It is the variability of the S1-S2 loops between NaV channels which contributes substantially to the selectivity profile observed for this toxin, particularly with regards to fast inactivation. This toxin may bind the channel in the resting state (Probable).
    """
    result4 = analyze_text_for_nav17(text4)


    print("\n" + "texto final" + "\n")
    text5 = """
       Neurotoxin that selectively inhibits neuronal tetrodotoxin-sensitive voltage-gated sodium channels (Nav) (IC50=44.6 nM) (PubMed:12518233, PubMed:14512091).
        It is active on Nav1.2/SCN2A (IC50=22.4 nM), Nav1.6/SCN8A (IC50=50.1 nM) and Nav1.7/SCN9A (IC50=48.9 nM) (PubMed:29703751).
        It shows low affinity for lipid bilayers (PubMed:29703751). """
    result5 = analyze_text_for_nav17(text5)
    
    print("\n" + "texto final" + "\n")
    text6 = """
    Gating-modifier toxin that both inhibits the peak current of human Nav1.1/SCN1A, rat Nav1.2/SCN2A, human Nav1.6/SCN8A, and human Nav1.7/SCN9A and concurrently inhibits fast inactivation of human Nav1.1 and rat Nav1.3/SCN3A. The relative rank order potency for Nav modulation is Nav1.3 (inactivation EC50=45 nM) > Nav1.7 > Nav1.2 > Nav1.1 (inactivation) > Nav1.1 > Nav1.6 > Nav1.3 (IC50=8 uM). The DII and DIV S3-S4 loops of Nav channel voltage sensors are important for the interaction of this toxin with Nav channels but cannot account for its unique subtype selectivity. It is the variability of the S1-S2 loops between NaV channels which contributes substantially to the selectivity profile observed for this toxin, particularmente con respecto a la rápida inactivación. Esta toxina puede unirse al canal en el estado de reposo (Probable)."""
    result6 = analyze_text_for_nav17(text6)
'''
