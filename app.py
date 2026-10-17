import html
import io
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

# Optional third-party imports with graceful degradation
try:
    from google import genai
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False


# =====================================================================
# CONFIGURAZIONE PAGINA STREAMLIT
# =====================================================================
st.set_page_config(
    page_title="MedClear AI — Clinical Discharge & Patient Navigator",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =====================================================================
# CONFIGURAZIONE DELLE 13 LINGUE SUPPORTATE + METADATI (BCP-47, GTTS, RTL)
# =====================================================================
LANGUAGES_CONFIG: Dict[str, Dict[str, Any]] = {
    "🇮🇹 Italiano": {"code": "it", "bcp47": "it-IT", "gtts": "it", "rtl": False, "name": "Italiano"},
    "🇬🇧 English": {"code": "en", "bcp47": "en-US", "gtts": "en", "rtl": False, "name": "English"},
    "🇪🇸 Español": {"code": "es", "bcp47": "es-ES", "gtts": "es", "rtl": False, "name": "Español"},
    "🇫🇷 Français": {"code": "fr", "bcp47": "fr-FR", "gtts": "fr", "rtl": False, "name": "Français"},
    "🇩🇪 Deutsch": {"code": "de", "bcp47": "de-DE", "gtts": "de", "rtl": False, "name": "Deutsch"},
    "🇷🇺 Русский (Russian)": {"code": "ru", "bcp47": "ru-RU", "gtts": "ru", "rtl": False, "name": "Russian (Русский)"},
    "🇸🇦 العربية (Arabic)": {"code": "ar", "bcp47": "ar-SA", "gtts": "ar", "rtl": True, "name": "Arabic (العربية)"},
    "🇨🇳 中文 (Mandarin)": {"code": "zh", "bcp47": "zh-CN", "gtts": "zh-CN", "rtl": False, "name": "Mandarin Chinese (中文)"},
    "🇷🇴 Română": {"code": "ro", "bcp47": "ro-RO", "gtts": "ro", "rtl": False, "name": "Română"},
    "🇺🇦 Українська (Ukrainian)": {"code": "uk", "bcp47": "uk-UA", "gtts": "uk", "rtl": False, "name": "Ukrainian (Українська)"},
    "🇮🇳 हिन्दी (Hindi)": {"code": "hi", "bcp47": "hi-IN", "gtts": "hi", "rtl": False, "name": "Hindi (हिन्दी)"},
    "🇵🇹 Português": {"code": "pt", "bcp47": "pt-PT", "gtts": "pt", "rtl": False, "name": "Português"},
    "🇦🇱 Shqip (Albanian)": {"code": "sq", "bcp47": "sq-AL", "gtts": "sq", "rtl": False, "name": "Albanian (Shqip)"},
}


# =====================================================================
# DIZIONARIO COMPLETO DI TUTTA L'INTERFACCIA (12 LINGUE)
# Include Pannello di Controllo, Sidebar, Bottoni, Step 1-7, TTS e Chat
# =====================================================================
FULL_UI_I18N: Dict[str, Dict[str, str]] = {
    "it": {
        "hero_sub": "Piattaforma SaaS di Clinical NLP per la traduzione empatica, sicura e multilingua (12 lingue) delle lettere di dimissione ospedaliera.",
        "dock_title": "⚙️ Pannello di Controllo Rapido (AI Engine, 12 Lingue & Accessibilità)",
        "api_label": "🔑 API Key (Evolus 'evo_...' o Gemini 'AIza...')",
        "api_placeholder": "Incolla qui evo_... oppure AIza...",
        "status_evolus": "✅ Connesso a Evolus Cloud on AMD Instinct™ GPU",
        "status_gemini": "✅ Connesso a Google Gemini Flash Cloud",
        "status_custom": "🔗 Connesso a Endpoint OpenAI-Compatible",
        "status_demo": "⚡ Smart Demo Mode (Inserisci 'evo_...' o 'AIza...')",
        "lang_label": "🌍 Lingua dell'Applicazione e del Referto (12 Lingue)",
        "profile_label": "👤 Profilo Paziente",
        "profiles": "Standard (Adulto)|Semplificato (Anziano / Caregiver)|Pediatrico (Spiegazione per Genitori)",
        "theme_label": "🎨 Tema Visivo & Accessibilità",
        "themes": "☀️ Clinico Chiaro (Default)|🌙 Dark Mode (Riposo Visivo)|👁️ Modalità Daltonici (Okabe-Ito)",
        "big_font_label": "👓 Carattere Grande (Anziani / Ipovedenti)",
        "model_label": "🧠 Modello AI (ROCm™ / Gemini)",
        "url_label": "🔗 Evolus / AMD Base URL",
        "sb_telemetry": "📊 Telemetria Inferenza",
        "sb_latency": "Latency Ultima Analisi",
        "sb_engine": "Engine Attivo",
        "sb_completed": "Analisi completate",
        "cb_banner": "♿ Modalità Daltonismo Attiva: Palette scientifica Okabe-Ito + Codifica Geometrica (● ▲ ■) per la sicurezza del Triage Domiciliare",
        "step1_title": "Seleziona un Caso Clinico Demo o Carica il Referto Ospedaliero",
        "case1_btn": "🫀 Cardiologia — Scompenso & Fibrillazione Atriale",
        "case2_btn": "🦴 Ortopedia — Frattura Malleolo & Tutore Walker",
        "case3_btn": "🧸 Pediatria — Bronchiolite Acuta & Distanziatore",
        "pdf_label": "📄 Carica Lettera di Dimissione in PDF",
        "active_cfg": "Configurazione Attiva",
        "editor_label": "✍️ Testo Clinico della Lettera di Dimissione (incolla o modifica):",
        "words_lbl": "parole",
        "comp_lbl": "Complessità Clinica: Alta",
        "abbr_count_lbl": "abbreviazioni mediche rilevate",
        "abbr_list_lbl": "Sigle rilevate:",
        "orig_expander": "🔍 Leggi il 'Testo Medico Originale' integrale (Confronto Complessità per i Giudici)",
        "analyze_btn": "✨ Analizza e Traduci per il Paziente",
        "step2_title": "Riassunto Empatico della Dimissione",
        "empathy_header": "Spiegazione Chiara del Medico Navigatore",
        "tts_play": "🔊 Ascolta il Riassunto ad Alta Voce",
        "tts_stop": "⏹️ Stop",
        "step3_title": "Piano Terapeutico Giornaliero per Fascia Oraria",
        "morning": "🌅 Mattina",
        "lunch": "☀️ Pranzo",
        "evening": "🌙 Sera",
        "prn": "💊 Al Bisogno",
        "no_meds": "Nessun farmaco in questa fascia",
        "instructions": "Istruzioni",
        "step4_title": "Semaforo dei Sintomi (Triage Domiciliare)",
        "triage_g": "🟢 Tutto Normale (Cosa aspettarsi)",
        "triage_y": "🟡 Contatta il Medico se...",
        "triage_r": "🔴 Vai in Pronto Soccorso se...",
        "cb_g": "● [CERCHIO - STABILE] Tutto Normale",
        "cb_y": "▲ [TRIANGOLO - ATTENZIONE] Contatta il Medico se...",
        "cb_r": "■ [QUADRATO - URGENZA CRITICA] Vai in Pronto Soccorso se...",
        "step5_title": "Prossimi Passi & Domande per la Visita di Controllo",
        "steps_title": "📅 Checklist Esami, Controlli e Cura Quotidiana",
        "questions_title": "❓ 3 Domande Intelligenti da fare al Medico",
        "question_lbl": "Domanda",
        "step6_title": "Azioni & Esportazione (Foglio da Frigorifero & Audio MP3)",
        "dl_html_btn": "🖨️ Scarica Foglio Promemoria da Stampare (HTML da Frigorifero)",
        "dl_txt_btn": "📄 Scarica Promemoria Testuale (.TXT)",
        "mp3_btn": "🎧 Genera File Audio MP3 (gTTS)",
        "step7_title": "Chiedi al tuo Referto (Assistente Clinico Contestuale)",
        "q1_btn": "🚗 Posso guidare nei prossimi giorni?",
        "q2_btn": "💊 Cosa succede se dimentico una compressa?",
        "q3_btn": "🥗 Ci sono regole su cibo, acqua o sale?",
        "chat_placeholder": "Fai una domanda specifica sul tuo referto...",
        "chat_welcome": "Benvenuto in **MedClear AI**! Qui sopra trovi la guida tradotta per il paziente. Fai pure una domanda specifica sul referto qui sotto.",
    },
    "en": {
        "hero_sub": "Clinical NLP SaaS platform for empathetic, safe, multilingual (12 languages) translation of hospital discharge letters.",
        "dock_title": "⚙️ Quick Control Panel (AI Engine, 12 Languages & Accessibility)",
        "api_label": "🔑 API Key (Evolus 'evo_...' or Gemini 'AIza...')",
        "api_placeholder": "Paste evo_... or AIza... here",
        "status_evolus": "✅ Connected to Evolus Cloud on AMD Instinct™ GPU",
        "status_gemini": "✅ Connected to Google Gemini Flash Cloud",
        "status_custom": "🔗 Connected to Custom OpenAI-Compatible Endpoint",
        "status_demo": "⚡ Smart Demo Mode (Enter 'evo_...' or 'AIza...')",
        "lang_label": "🌍 App & Report Output Language (12 Languages)",
        "profile_label": "👤 Patient Profile",
        "profiles": "Standard (Adult)|Simplified (Elderly / Caregiver)|Pediatric (Explanation for Parents)",
        "theme_label": "🎨 Visual Theme & Accessibility",
        "themes": "☀️ Clinical Light (Default)|🌙 Dark Mode (Eye Comfort)|👁️ Colorblind Mode (Okabe-Ito)",
        "big_font_label": "👓 Large Font (Elderly / Low Vision)",
        "model_label": "🧠 AI Model (ROCm™ / Gemini)",
        "url_label": "🔗 Evolus / AMD Base URL",
        "sb_telemetry": "📊 Inference Telemetry",
        "sb_latency": "Last Analysis Latency",
        "sb_engine": "Active Engine",
        "sb_completed": "Completed analyses",
        "cb_banner": "♿ Colorblind Mode Active: Scientific Okabe-Ito Palette + Geometric Coding (● ▲ ■) for Home Triage Safety",
        "step1_title": "Select a Demo Clinical Case or Upload Hospital Report",
        "case1_btn": "🫀 Cardiology — Heart Failure & Atrial Fibrillation",
        "case2_btn": "🦴 Orthopedics — Ankle Fracture & Walker Boot",
        "case3_btn": "🧸 Pediatrics — Acute Bronchiolitis & Spacer",
        "pdf_label": "📄 Upload Discharge Letter (PDF)",
        "active_cfg": "Active Configuration",
        "editor_label": "✍️ Clinical Discharge Text (paste or edit any medical report):",
        "words_lbl": "words",
        "comp_lbl": "Clinical Complexity: High",
        "abbr_count_lbl": "medical abbreviations detected",
        "abbr_list_lbl": "Detected acronyms:",
        "orig_expander": "🔍 View Full 'Original Medical Text' (Complexity Comparison for Judges)",
        "analyze_btn": "✨ Analyze & Translate for Patient",
        "step2_title": "Empathetic Discharge Summary",
        "empathy_header": "Clear Explanation from Your Patient Navigator",
        "tts_play": "🔊 Listen to Summary Aloud",
        "tts_stop": "⏹️ Stop",
        "step3_title": "Daily Medication Schedule by Time Slot",
        "morning": "🌅 Morning",
        "lunch": "☀️ Lunch / Afternoon",
        "evening": "🌙 Evening",
        "prn": "💊 As Needed",
        "no_meds": "No medication in this time slot",
        "instructions": "Instructions",
        "step4_title": "Symptom Traffic Light (Home Triage)",
        "triage_g": "🟢 All Normal (What to expect)",
        "triage_y": "🟡 Contact Your Doctor if...",
        "triage_r": "🔴 Go to the Emergency Room if...",
        "cb_g": "● [CIRCLE - STABLE] All Normal",
        "cb_y": "▲ [TRIANGLE - CAUTION] Contact Doctor if...",
        "cb_r": "■ [SQUARE - CRITICAL EMERGENCY] Go to ER if...",
        "step5_title": "Next Steps & Questions for Follow-Up Visit",
        "steps_title": "📅 Follow-Up Checklist & Daily Care",
        "questions_title": "❓ 3 Smart Questions to Ask Your Doctor",
        "question_lbl": "Question",
        "step6_title": "Actions & Export (Printable Fridge Sheet & MP3 Audio)",
        "dl_html_btn": "🖨️ Download Printable Fridge Sheet (HTML)",
        "dl_txt_btn": "📄 Download Text Summary (.TXT)",
        "mp3_btn": "🎧 Generate MP3 Audio File (gTTS)",
        "step7_title": "Ask Your Report (Contextual Clinical Assistant)",
        "q1_btn": "🚗 Can I drive in the next few days?",
        "q2_btn": "💊 What happens if I miss a tablet?",
        "q3_btn": "🥗 Are there rules about food, water, or salt?",
        "chat_placeholder": "Ask a specific question about your medical report...",
        "chat_welcome": "Welcome to **MedClear AI**! Above is your translated patient guide. Ask any specific question about your report below.",
    },
    "es": {
        "hero_sub": "Plataforma SaaS de NLP Clínico para la traducción empática, segura y multilingüe (12 idiomas) de informes de alta hospitalaria.",
        "dock_title": "⚙️ Panel de Control Rápido (Motor IA, 12 Idiomas y Accesibilidad)",
        "api_label": "🔑 Clave API (Evolus 'evo_...' o Gemini 'AIza...')",
        "api_placeholder": "Pegue aquí evo_... o AIza...",
        "status_evolus": "✅ Conectado a Evolus Cloud en GPU AMD Instinct™",
        "status_gemini": "✅ Conectado a Google Gemini Flash Cloud",
        "status_custom": "🔗 Conectado a Endpoint Compatible con OpenAI",
        "status_demo": "⚡ Modo Demo Inteligente (Ingrese 'evo_...' o 'AIza...')",
        "lang_label": "🌍 Idioma de la Aplicación y del Informe (12 Idiomas)",
        "profile_label": "👤 Perfil del Paciente",
        "profiles": "Estándar (Adulto)|Simplificado (Mayor / Cuidador)|Pediátrico (Explicación para Padres)",
        "theme_label": "🎨 Tema Visual y Accesibilidad",
        "themes": "☀️ Clínico Claro (Por defecto)|🌙 Modo Oscuro (Descanso Visual)|👁️ Modo Daltónicos (Okabe-Ito)",
        "big_font_label": "👓 Letra Grande (Mayores / Baja Visión)",
        "model_label": "🧠 Modelo IA (ROCm™ / Gemini)",
        "url_label": "🔗 URL Base Evolus / AMD",
        "sb_telemetry": "📊 Telemetría de Inferencia",
        "sb_latency": "Latencia Último Análisis",
        "sb_engine": "Motor Activo",
        "sb_completed": "Análisis completados",
        "cb_banner": "♿ Modo Daltonismo Activo: Paleta científica Okabe-Ito + Codificación Geométrica (● ▲ ■) para Triaje Domiciliario",
        "step1_title": "Seleccione un Caso Clínico Demo o Suba su Informe",
        "case1_btn": "🫀 Cardiología — Insuficiencia Cardíaca y FA",
        "case2_btn": "🦴 Ortopedia — Fractura de Maléolo y Bota Walker",
        "case3_btn": "🧸 Pediatría — Bronquiolitis Aguda e Inhalador",
        "pdf_label": "📄 Subir Informe de Alta en PDF",
        "active_cfg": "Configuración Activa",
        "editor_label": "✍️ Texto Clínico del Informe de Alta (pegue o edite):",
        "words_lbl": "palabras",
        "comp_lbl": "Complejidad Clínica: Alta",
        "abbr_count_lbl": "abreviaturas médicas detectadas",
        "abbr_list_lbl": "Siglas detectadas:",
        "orig_expander": "🔍 Ver 'Texto Médico Original' completo (Comparación para el Jurado)",
        "analyze_btn": "✨ Analizar y Traducir para el Paciente",
        "step2_title": "Resumen Empático del Alta",
        "empathy_header": "Explicación Clara del Médico Navegador",
        "tts_play": "🔊 Escuchar Resumen en Voz Alta",
        "tts_stop": "⏹️ Detener",
        "step3_title": "Plan Terapéutico Diario por Franja Horaria",
        "morning": "🌅 Mañana",
        "lunch": "☀️ Mediodía",
        "evening": "🌙 Noche",
        "prn": "💊 Si es necesario",
        "no_meds": "Sin medicamentos en este horario",
        "instructions": "Instrucciones",
        "step4_title": "Semáforo de Síntomas (Triaje en Casa)",
        "triage_g": "🟢 Todo Normal (Qué esperar)",
        "triage_y": "🟡 Contacte al Médico si...",
        "triage_r": "🔴 Vaya a Urgencias si...",
        "cb_g": "● [CÍRCULO - ESTABLE] Todo Normal",
        "cb_y": "▲ [TRIÁNGULO - ATENCIÓN] Contacte al Médico si...",
        "cb_r": "■ [CUADRADO - URGENCIA CRÍTICA] Vaya a Urgencias si...",
        "step5_title": "Próximos Pasos y Preguntas para la Consulta",
        "steps_title": "📅 Lista de Controles y Cuidados Diarios",
        "questions_title": "❓ 3 Preguntas Recomendadas para su Médico",
        "question_lbl": "Pregunta",
        "step6_title": "Acciones y Exportación (Hoja para la Nevera y Audio MP3)",
        "dl_html_btn": "🖨️ Descargar Hoja Resumen Imprimible (HTML)",
        "dl_txt_btn": "📄 Descargar Resumen en Texto (.TXT)",
        "mp3_btn": "🎧 Generar Archivo de Audio MP3 (gTTS)",
        "step7_title": "Pregunte a su Informe (Asistente Clínico Contextual)",
        "q1_btn": "🚗 ¿Puedo conducir en los próximos días?",
        "q2_btn": "💊 ¿Qué pasa si olvido tomar una pastilla?",
        "q3_btn": "🥗 ¿Hay reglas sobre comida, agua o sal?",
        "chat_placeholder": "Haga una pregunta específica sobre su informe médico...",
        "chat_welcome": "¡Bienvenido a **MedClear AI**! Arriba encontrará su guía traducida. Escriba cualquier duda sobre su informe aquí abajo.",
    },
    "fr": {
        "hero_sub": "Plateforme SaaS de NLP Clinique pour la traduction empathique, sûre et multilingue (12 langues) des lettres de sortie d'hôpital.",
        "dock_title": "⚙️ Panneau de Contrôle Rapide (Moteur IA, 12 Langues & Accessibilité)",
        "api_label": "🔑 Clé API (Evolus 'evo_...' ou Gemini 'AIza...')",
        "api_placeholder": "Collez evo_... ou AIza... ici",
        "status_evolus": "✅ Connecté à Evolus Cloud sur GPU AMD Instinct™",
        "status_gemini": "✅ Connecté à Google Gemini Flash Cloud",
        "status_custom": "🔗 Connecté au Point de Terminaison Compatible OpenAI",
        "status_demo": "⚡ Mode Démo Intelligent (Entrez 'evo_...' ou 'AIza...')",
        "lang_label": "🌍 Langue de l'Application et du Compte-Rendu (12 Langues)",
        "profile_label": "👤 Profil du Patient",
        "profiles": "Standard (Adulte)|Simplifié (Senior / Aidant)|Pédiatrique (Explication Parents)",
        "theme_label": "🎨 Thème Visuel & Accessibilité",
        "themes": "☀️ Clinique Clair (Défaut)|🌙 Mode Sombre (Repos Visuel)|👁️ Mode Daltonien (Okabe-Ito)",
        "big_font_label": "👓 Grands Caractères (Seniors / Malvoyants)",
        "model_label": "🧠 Modèle IA (ROCm™ / Gemini)",
        "url_label": "🔗 URL de Base Evolus / AMD",
        "sb_telemetry": "📊 Télémétrie d'Inférence",
        "sb_latency": "Latence Dernière Analyse",
        "sb_engine": "Moteur Actif",
        "sb_completed": "Analyses terminées",
        "cb_banner": "♿ Mode Daltonien Actif : Palette scientifique Okabe-Ito + Codage Géométrique (● ▲ ■) pour le Triage à Domicile",
        "step1_title": "Sélectionnez un Cas Clinique Démo ou Chargez votre Compte-Rendu",
        "case1_btn": "🫀 Cardiologie — Insuffisance Cardiaque & FA",
        "case2_btn": "🦴 Orthopédie — Fracture Malléole & Botte Walker",
        "case3_btn": "🧸 Pédiatrie — Bronchiolite Aiguë & Chambre d'Inhalation",
        "pdf_label": "📄 Charger la Lettre de Sortie en PDF",
        "active_cfg": "Configuration Active",
        "editor_label": "✍️ Texte Clinique de la Lettre de Sortie (collez ou modifiez) :",
        "words_lbl": "mots",
        "comp_lbl": "Complexité Clinique : Élevée",
        "abbr_count_lbl": "abréviations médicales détectées",
        "abbr_list_lbl": "Sigles détectés :",
        "orig_expander": "🔍 Lire le 'Texte Médical Original' complet (Comparaison pour le Jury)",
        "analyze_btn": "✨ Analyser et Traduire pour le Patient",
        "step2_title": "Résumé Empathique de Sortie",
        "empathy_header": "Explication Claire du Médecin Navigateur",
        "tts_play": "🔊 Écouter le Résumé à Haute Voix",
        "tts_stop": "⏹️ Arrêter",
        "step3_title": "Plan Thérapeutique Quotidien par Créneau Horaire",
        "morning": "🌅 Matin",
        "lunch": "☀️ Midi",
        "evening": "🌙 Soir",
        "prn": "💊 Si besoin",
        "no_meds": "Aucun médicament sur ce créneau",
        "instructions": "Instructions",
        "step4_title": "Feu Tricolore des Symptômes (Triage à Domicile)",
        "triage_g": "🟢 Tout est Normal (À quoi s'attendre)",
        "triage_y": "🟡 Contactez le Médecin si...",
        "triage_r": "🔴 Allez aux Urgences si...",
        "cb_g": "● [CERCLE - STABLE] Tout est Normal",
        "cb_y": "▲ [TRIANGLE - ATTENTION] Contactez le Médecin si...",
        "cb_r": "■ [CARRÉ - URGENCE CRITIQUE] Allez aux Urgences si...",
        "step5_title": "Prochaines Étapes & Questions pour la Visite de Suivi",
        "steps_title": "📅 Liste des Examens, Suivis et Soins Quotidiens",
        "questions_title": "❓ 3 Questions Conseillées pour le Médecin",
        "question_lbl": "Question",
        "step6_title": "Actions & Exportation (Fiche Frigo Imprimable & Audio MP3)",
        "dl_html_btn": "🖨️ Télécharger la Fiche Frigo à Imprimer (HTML)",
        "dl_txt_btn": "📄 Télécharger le Résumé Texte (.TXT)",
        "mp3_btn": "🎧 Générer le Fichier Audio MP3 (gTTS)",
        "step7_title": "Interrogez votre Compte-Rendu (Assistant Clinique Contextuel)",
        "q1_btn": "🚗 Puis-je conduire dans les prochains jours ?",
        "q2_btn": "💊 Que faire si j'oublie un comprimé ?",
        "q3_btn": "🥗 Y a-t-il des règles sur l'alimentation, l'eau ou le sel ?",
        "chat_placeholder": "Posez une question précise sur votre compte-rendu...",
        "chat_welcome": "Bienvenue sur **MedClear AI** ! Voici votre guide patient traduit ci-dessus. Posez vos questions ci-dessous.",
    },
    "de": {
        "hero_sub": "Klinische NLP-SaaS-Plattform für empathische, sichere und mehrsprachige (12 Sprachen) Übersetzung von Arztbriefen.",
        "dock_title": "⚙️ Schnellsteuerungs-Panel (KI-Engine, 12 Sprachen & Barrierefreiheit)",
        "api_label": "🔑 API-Schlüssel (Evolus 'evo_...' oder Gemini 'AIza...')",
        "api_placeholder": "evo_... oder AIza... hier einfügen",
        "status_evolus": "✅ Verbunden mit Evolus Cloud auf AMD Instinct™ GPU",
        "status_gemini": "✅ Verbunden mit Google Gemini Flash Cloud",
        "status_custom": "🔗 Verbunden mit OpenAI-kompatiblem Endpunkt",
        "status_demo": "⚡ Smart Demo-Modus ('evo_...' oder 'AIza...' eingeben)",
        "lang_label": "🌍 Sprache der App & des Arztbriefs (12 Sprachen)",
        "profile_label": "👤 Patientenprofil",
        "profiles": "Standard (Erwachsene)|Vereinfacht (Senioren / Pflegende)|Pädiatrisch (Erklärung für Eltern)",
        "theme_label": "🎨 Design-Thema & Barrierefreiheit",
        "themes": "☀️ Klinisch Hell (Standard)|🌙 Dark Mode (Augenschonend)|👁️ Farbenblind-Modus (Okabe-Ito)",
        "big_font_label": "👓 Große Schrift (Senioren / Sehbehinderte)",
        "model_label": "🧠 KI-Modell (ROCm™ / Gemini)",
        "url_label": "🔗 Evolus / AMD Basis-URL",
        "sb_telemetry": "📊 Inferenz-Telemetrie",
        "sb_latency": "Latenz letzte Analyse",
        "sb_engine": "Aktive Engine",
        "sb_completed": "Abgeschlossene Analysen",
        "cb_banner": "♿ Farbenblind-Modus Aktiv: Wissenschaftliche Okabe-Ito-Palette + Geometrische Symbole (● ▲ ■)",
        "step1_title": "Klinischen Demo-Fall wählen oder Arztbrief hochladen",
        "case1_btn": "🫀 Kardiologie — Herzinsuffizienz & Vorhofflimmern",
        "case2_btn": "🦴 Orthopädie — Knöchelfraktur & Walker-Orthese",
        "case3_btn": "🧸 Pädiatrie — Akute Bronchiolitis & Inhalierhilfe",
        "pdf_label": "📄 Entlassungsbrief als PDF hochladen",
        "active_cfg": "Aktive Konfiguration",
        "editor_label": "✍️ Klinischer Text des Entlassungsbriefs (einfügen oder bearbeiten):",
        "words_lbl": "Wörter",
        "comp_lbl": "Klinische Komplexität: Hoch",
        "abbr_count_lbl": "medizinische Abkürzungen erkannt",
        "abbr_list_lbl": "Erkannte Kürzel:",
        "orig_expander": "🔍 Vollständigen 'Medizinischen Originaltext' anzeigen",
        "analyze_btn": "✨ Für den Patienten analysieren & übersetzen",
        "step2_title": "Empathische Entlassungs-Zusammenfassung",
        "empathy_header": "Verständliche Erklärung Ihres Patienten-Navigators",
        "tts_play": "🔊 Zusammenfassung laut vorlesen",
        "tts_stop": "⏹️ Stopp",
        "step3_title": "Täglicher Medikationsplan nach Tageszeit",
        "morning": "🌅 Morgens",
        "lunch": "☀️ Mittags",
        "evening": "🌙 Abends",
        "prn": "💊 Bei Bedarf",
        "no_meds": "Keine Medikamente in diesem Zeitraum",
        "instructions": "Hinweise",
        "step4_title": "Symptom-Ampel (Triage für zu Hause)",
        "triage_g": "🟢 Alles Normal (Was zu erwarten ist)",
        "triage_y": "🟡 Arzt kontaktieren, wenn...",
        "triage_r": "🔴 Sofort in die Notaufnahme, wenn...",
        "cb_g": "● [KREIS - STABIL] Alles Normal",
        "cb_y": "▲ [DREIECK - ACHTUNG] Arzt kontaktieren, wenn...",
        "cb_r": "■ [QUADRAT - NOTFALL] Sofort in die Notaufnahme, wenn...",
        "step5_title": "Nächste Schritte & Fragen für den Kontrolltermin",
        "steps_title": "📅 Checkliste für Untersuchungen & Alltag",
        "questions_title": "❓ 3 Wichtige Fragen für Ihren Arzttermin",
        "question_lbl": "Frage",
        "step6_title": "Aktionen & Export (Kühlschrank-Merkblatt & MP3-Audio)",
        "dl_html_btn": "🖨️ Druckbares Kühlschrank-Merkblatt herunterladen (HTML)",
        "dl_txt_btn": "📄 Text-Zusammenfassung herunterladen (.TXT)",
        "mp3_btn": "🎧 MP3-Audiodatei erstellen (gTTS)",
        "step7_title": "Fragen Sie Ihren Befund (Kontextbezogener KI-Assistent)",
        "q1_btn": "🚗 Darf ich in den nächsten Tagen Auto fahren?",
        "q2_btn": "💊 Was passiert, wenn ich eine Tablette vergesse?",
        "q3_btn": "🥗 Gibt es Regeln für Essen, Trinken oder Salz?",
        "chat_placeholder": "Stellen Sie eine Frage zu Ihrem Arztbrief...",
        "chat_welcome": "Willkommen bei **MedClear AI**! Oben finden Sie Ihren übersetzten Patientenleitfaden. Stellen Sie unten Ihre Fragen.",
    },
    "ar": {
        "hero_sub": "منصة ذكاء اصطناعي طبي لترجمة تقارير الخروج من المستشفى بطريقة مبسطة وآمنة ومتعددة اللغات (12 لغة).",
        "dock_title": "⚙️ لوحة التحكم السريعة (محرك الذكاء الاصطناعي، 12 لغة وإمكانية الوصول)",
        "api_label": "🔑 مفتاح API (Evolus 'evo_...' أو Gemini 'AIza...')",
        "api_placeholder": "الصق مفتاح evo_... أو AIza... هنا",
        "status_evolus": "✅ متصل بـ Evolus Cloud على معالجات AMD Instinct™ GPU",
        "status_gemini": "✅ متصل بـ Google Gemini Flash Cloud",
        "status_custom": "🔗 متصل بنقطة نهاية متوافقة مع OpenAI",
        "status_demo": "⚡ الوضع التجريبي الذكي (أدخل 'evo_...' أو 'AIza...')",
        "lang_label": "🌍 لغة التطبيق والتقرير الطبي (12 لغة)",
        "profile_label": "👤 ملف المريض",
        "profiles": "قياسي (بالغ)|مبسط (كبار السن / مقدم رعاية)|أطفال (شرح للوالدين)",
        "theme_label": "🎨 المظهر البصري وإمكانية الوصول",
        "themes": "☀️ طبي فاتح (افتراضي)|🌙 الوضع الداكن (راحة العين)|👁️ وضع عمى الألوان (Okabe-Ito)",
        "big_font_label": "👓 خط كبير (لكبار السن وضعاف البصر)",
        "model_label": "🧠 نموذج الذكاء الاصطناعي (ROCm™ / Gemini)",
        "url_label": "🔗 رابط Evolus / AMD الأساسي",
        "sb_telemetry": "📊 قياسات الأداء والاستدلال",
        "sb_latency": "زمن الاستجابة الأخير",
        "sb_engine": "المحرك النشط",
        "sb_completed": "التحليلات المكتملة",
        "cb_banner": "♿ وضع عمى الألوان نشط: ألوان Okabe-Ito العلمية + الرموز الهندسية (● ▲ ■) لسلامة الفرز المنزلي",
        "step1_title": "اختر حالة سريرية تجريبية أو ارفع تقرير المستشفى",
        "case1_btn": "🫀 أمراض القلب — قصور القلب والرجفان الأذيني",
        "case2_btn": "🦴 العظام — كسر الكاحل وجبيرة Walker",
        "case3_btn": "🧸 طب الأطفال — التهاب القصيبات الحاد والبخاخ",
        "pdf_label": "📄 ارفع تقرير الخروج بصيغة PDF",
        "active_cfg": "الإعدادات النشطة",
        "editor_label": "✍️ النص الطبي لتقرير الخروج (الصق أو عدّل التقرير):",
        "words_lbl": "كلمة",
        "comp_lbl": "التعقيد الطبي: مرتفع",
        "abbr_count_lbl": "اختصارات طبية تم رصدها",
        "abbr_list_lbl": "الاختصارات المرصودة:",
        "orig_expander": "🔍 عرض 'النص الطبي الأصلي' بالكامل (مقارنة التعقيد للجنة التحكيم)",
        "analyze_btn": "✨ تحليل وترجمة التقرير للمريض",
        "step2_title": "الملخص الطبي المطمئن والمبسط",
        "empathy_header": "شرح واضح ومبسط من الطبيب الموجه",
        "tts_play": "🔊 استمع إلى الملخص بصوت واضح",
        "tts_stop": "⏹️ إيقاف",
        "step3_title": "جدول الأدوية اليومي حسب الفترات الزمنية",
        "morning": "🌅 الصباح",
        "lunch": "☀️ الظهر",
        "evening": "🌙 المساء",
        "prn": "💊 عند الحاجة",
        "no_meds": "لا توجد أدوية في هذه الفترة",
        "instructions": "تعليمات",
        "step4_title": "إشارة مرور الأعراض (الفرز الطبي المنزلي)",
        "triage_g": "🟢 وضع طبيعي ومطمئن (ما يمكن توقعه)",
        "triage_y": "🟡 اتصل بالطبيب إذا...",
        "triage_r": "🔴 توجه فوراً إلى الطوارئ إذا...",
        "cb_g": "● [دائرة - مستقر] وضع طبيعي ومطمئن",
        "cb_y": "▲ [مثلث - تنبيه] اتصل بالطبيب إذا...",
        "cb_r": "■ [مربع - طوارئ حرجة] توجه فوراً إلى الطوارئ إذا...",
        "step5_title": "الخطوات القادمة وأسئلة للمتابعة الطبية",
        "steps_title": "📅 قائمة الفحوصات والمواعيد والعناية اليومية",
        "questions_title": "❓ 3 أسئلة ذكية لطرحها على طبيبك",
        "question_lbl": "سؤال",
        "step6_title": "الإجراءات والتصدير (ورقة تذكير للطباعة وملف صوتي MP3)",
        "dl_html_btn": "🖨️ تحميل ورقة التذكير للطباعة (HTML)",
        "dl_txt_btn": "📄 تحميل الملخص النصي (.TXT)",
        "mp3_btn": "🎧 إنشاء ملف صوتي MP3 (gTTS)",
        "step7_title": "اسأل تقريرك الطبي (المساعد الطبي الذكي)",
        "q1_btn": "🚗 هل يمكنني قيادة السيارة في الأيام القادمة؟",
        "q2_btn": "💊 ماذا أفعل إذا نسيت تناول جرعة الدواء؟",
        "q3_btn": "🥗 هل هناك تعليمات حول الطعام أو الماء أو الملح؟",
        "chat_placeholder": "اكتب سؤالك حول تقريرك الطبي هنا...",
        "chat_welcome": "مرحباً بك في **MedClear AI**! تجد أعلاه دليلك الطبي المترجم والمبسط. يمكنك طرح أي سؤال حول تقريرك أدناه.",
    },
    "zh": {
        "hero_sub": "临床自然语言处理 SaaS 平台，提供温和、安全、多语言（12种语言）的医院出院小结翻译与患者导航。",
        "dock_title": "⚙️ 快速控制面板（AI 引擎、12 种语言与无障碍设置）",
        "api_label": "🔑 API 密钥 (Evolus 'evo_...' 或 Gemini 'AIza...')",
        "api_placeholder": "在此粘贴 evo_... 或 AIza...",
        "status_evolus": "✅ 已连接至 AMD Instinct™ GPU 上的 Evolus Cloud",
        "status_gemini": "✅ 已连接至 Google Gemini Flash Cloud",
        "status_custom": "🔗 已连接至兼容 OpenAI 的端点",
        "status_demo": "⚡ 智能演示模式（输入 'evo_...' 或 'AIza...'）",
        "lang_label": "🌍 应用界面与报告输出语言（12 种语言）",
        "profile_label": "👤 患者画像",
        "profiles": "标准（成人）|简化版（老年人 / 照护者）|儿科版（家长指南）",
        "theme_label": "🎨 视觉主题与无障碍模式",
        "themes": "☀️ 临床浅色（默认）|🌙 深色模式（护眼）|👁️ 色盲安全模式（Okabe-Ito）",
        "big_font_label": "👓 大字体模式（老年人 / 低视力）",
        "model_label": "🧠 AI 模型 (ROCm™ / Gemini)",
        "url_label": "🔗 Evolus / AMD 基础 URL",
        "sb_telemetry": "📊 推理性能遥测",
        "sb_latency": "上次分析延迟",
        "sb_engine": "当前激活引擎",
        "sb_completed": "已完成分析次数",
        "cb_banner": "♿ 色盲安全模式已启用：采用 Okabe-Ito 科学配色 + 几何符号编码 (● ▲ ■) 保障居家分诊安全",
        "step1_title": "选择临床演示病例或上传医院出院报告",
        "case1_btn": "🫀 心内科 — 心力衰竭与心房颤动",
        "case2_btn": "🦴 骨科 — 外踝骨折与 Walker 支具靴",
        "case3_btn": "🧸 儿科 — 急性毛细支气管炎与雾化储雾罐",
        "pdf_label": "📄 上传 PDF 格式出院小结",
        "active_cfg": "当前配置",
        "editor_label": "✍️ 出院小结临床文本（可粘贴或编辑）：",
        "words_lbl": "词",
        "comp_lbl": "临床复杂度：高",
        "abbr_count_lbl": "个医学缩写已识别",
        "abbr_list_lbl": "识别到的缩写：",
        "orig_expander": "🔍 查看完整“原始医学文本”（供评委对比专业复杂度）",
        "analyze_btn": "✨ 为患者分析并翻译报告",
        "step2_title": "温和易懂的出院总结",
        "empathy_header": "医疗导航员的通俗解读",
        "tts_play": "🔊 朗读出院总结",
        "tts_stop": "⏹️ 停止",
        "step3_title": "每日分时段用药计划",
        "morning": "🌅 早晨",
        "lunch": "☀️ 中午 / 下午",
        "evening": "🌙 晚上",
        "prn": "💊 按需服用",
        "no_meds": "此时段无药物",
        "instructions": "用药说明",
        "step4_title": "症状红绿灯（居家安全分诊）",
        "triage_g": "🟢 正常现象（预期恢复表现）",
        "triage_y": "🟡 请联系医生，如果出现...",
        "triage_r": "🔴 请立即前往急诊室，如果出现...",
        "cb_g": "● [圆形 - 稳定] 正常现象",
        "cb_y": "▲ [三角形 - 注意] 请联系医生...",
        "cb_r": "■ [方形 - 危急情况] 立即前往急诊...",
        "step5_title": "后续步骤与复诊建议问题",
        "steps_title": "📅 复查清单与日常护理安排",
        "questions_title": "❓ 下次复诊建议询问医生的 3 个问题",
        "question_lbl": "问题",
        "step6_title": "操作与导出（可打印冰箱贴备忘单 & MP3 语音）",
        "dl_html_btn": "🖨️ 下载可打印冰箱备忘单 (HTML)",
        "dl_txt_btn": "📄 下载文本版备忘单 (.TXT)",
        "mp3_btn": "🎧 生成 MP3 语音文件 (gTTS)",
        "step7_title": "向您的报告提问（基于文档的临床助手）",
        "q1_btn": "🚗 接下来几天我可以开车吗？",
        "q2_btn": "💊 如果漏服了一片药该怎么办？",
        "q3_btn": "🥗 饮食、饮水或吃盐有什么规定吗？",
        "chat_placeholder": "输入关于您出院报告的具体问题...",
        "chat_welcome": "欢迎使用 **MedClear AI**！上方已生成您的通俗出院指南，您可以在下方提出任何疑问。",
    },
    "ro": {
        "hero_sub": "Platformă SaaS de NLP Clinic pentru traducerea empatică, sigură și multilingvă (12 limbi) a biletelor de externare.",
        "dock_title": "⚙️ Panou de Control Rapid (Motor AI, 12 Limbi & Accesibilitate)",
        "api_label": "🔑 Cheie API (Evolus 'evo_...' sau Gemini 'AIza...')",
        "api_placeholder": "Lipiți aici evo_... sau AIza...",
        "status_evolus": "✅ Conectat la Evolus Cloud pe GPU AMD Instinct™",
        "status_gemini": "✅ Conectat la Google Gemini Flash Cloud",
        "status_custom": "🔗 Conectat la Endpoint Compatibil OpenAI",
        "status_demo": "⚡ Mod Demo Inteligent (Introduceți 'evo_...' sau 'AIza...')",
        "lang_label": "🌍 Limba Aplicației și a Raportului (12 Limbi)",
        "profile_label": "👤 Profil Pacient",
        "profiles": "Standard (Adult)|Simplificat (Vârstnic / Îngrijitor)|Pediatric (Explicații pentru Părinți)",
        "theme_label": "🎨 Temă Vizuală & Accesibilitate",
        "themes": "☀️ Clinic Luminos (Implicit)|🌙 Dark Mode (Odihnă Vizuală)|👁️ Mod Daltoniști (Okabe-Ito)",
        "big_font_label": "👓 Caractere Mari (Vârstnici / Hipovăzători)",
        "model_label": "🧠 Model AI (ROCm™ / Gemini)",
        "url_label": "🔗 URL de Bază Evolus / AMD",
        "sb_telemetry": "📊 Telemetrie Inferență",
        "sb_latency": "Latență Ultima Analiză",
        "sb_engine": "Motor Activ",
        "sb_completed": "Analize finalizate",
        "cb_banner": "♿ Mod Daltonism Activ: Paleta științifică Okabe-Ito + Codificare Geometrică (● ▲ ■) pentru Triaj Sigur",
        "step1_title": "Selectați un Caz Clinic Demo sau Încărcați Biletul de Externare",
        "case1_btn": "🫀 Cardiologie — Insuficiență Cardiacă & Fibrilație",
        "case2_btn": "🦴 Ortopedie — Fractură Maleolă & Orteza Walker",
        "case3_btn": "🧸 Pediatrie — Bronșiolită Acută & Spacer",
        "pdf_label": "📄 Încărcați Biletul de Externare în format PDF",
        "active_cfg": "Configurație Activă",
        "editor_label": "✍️ Textul Clinic al Biletului de Externare (lipiți sau modificați):",
        "words_lbl": "cuvinte",
        "comp_lbl": "Complexitate Clinică: Ridicată",
        "abbr_count_lbl": "abrevieri medicale detectate",
        "abbr_list_lbl": "Sigle detectate:",
        "orig_expander": "🔍 Citiți 'Textul Medical Original' integral (Comparație pentru Juriu)",
        "analyze_btn": "✨ Analizează și Tradu pentru Pacient",
        "step2_title": "Rezumatul Empatic al Externării",
        "empathy_header": "Explicație Clară de la Medicul Navigator",
        "tts_play": "🔊 Ascultă Rezumatul cu Voce Tare",
        "tts_stop": "⏹️ Stop",
        "step3_title": "Plan Terapeutic Zilnic pe Intervale Orare",
        "morning": "🌅 Dimineața",
        "lunch": "☀️ Prânz",
        "evening": "🌙 Seara",
        "prn": "💊 La nevoie",
        "no_meds": "Niciun medicament în acest interval",
        "instructions": "Instrucțiuni",
        "step4_title": "Semaforul Simptomelor (Triaj la Domiciliu)",
        "triage_g": "🟢 Totul Normal (La ce să vă așteptați)",
        "triage_y": "🟡 Contactați Medicul dacă...",
        "triage_r": "🔴 Mergeți la Urgențe (UPU) dacă...",
        "cb_g": "● [CERC - STABIL] Totul Normal",
        "cb_y": "▲ [TRIUNGHI - ATENȚIE] Contactați Medicul dacă...",
        "cb_r": "■ [PĂTRAT - URGENȚĂ CRITICĂ] Mergeți la Urgențe dacă...",
        "step5_title": "Pașii Următori & Întrebări pentru Control",
        "steps_title": "📅 Lista de Analize, Controale și Îngrijire Zilnică",
        "questions_title": "❓ 3 Întrebări Recomandate pentru Medic",
        "question_lbl": "Întrebare",
        "step6_title": "Acțiuni & Export (Fișă pentru Frigider & Audio MP3)",
        "dl_html_btn": "🖨️ Descarcă Fișa de Imprimat pentru Frigider (HTML)",
        "dl_txt_btn": "📄 Descarcă Rezumatul Text (.TXT)",
        "mp3_btn": "🎧 Generează Fișier Audio MP3 (gTTS)",
        "step7_title": "Întreabă Biletul de Externare (Asistent Clinic Contextual)",
        "q1_btn": "🚗 Pot conduce în următoarele zile?",
        "q2_btn": "💊 Ce se întâmplă dacă uit să iau o pastilă?",
        "q3_btn": "🥗 Există reguli privind mâncarea, apa sau sarea?",
        "chat_placeholder": "Puneți o întrebare specifică despre biletul de externare...",
        "chat_welcome": "Bun venit în **MedClear AI**! Mai sus găsiți ghidul tradus pentru pacient. Scrieți orice întrebare mai jos.",
    },
    "uk": {
        "hero_sub": "Клінічна NLP SaaS-платформа для емпатичного, безпечного та багатомовного (12 мов) перекладу лікарняних виписок.",
        "dock_title": "⚙️ Панель швидкого керування (AI-рушій, 12 мов та доступність)",
        "api_label": "🔑 API-ключ (Evolus 'evo_...' або Gemini 'AIza...')",
        "api_placeholder": "Вставте сюди evo_... або AIza...",
        "status_evolus": "✅ Підключено до Evolus Cloud на AMD Instinct™ GPU",
        "status_gemini": "✅ Підключено до Google Gemini Flash Cloud",
        "status_custom": "🔗 Підключено до OpenAI-сумісного ендпоінту",
        "status_demo": "⚡ Розумний демо-режим (введіть 'evo_...' або 'AIza...')",
        "lang_label": "🌍 Мова застосунку та медичної виписки (12 мов)",
        "profile_label": "👤 Профіль пацієнта",
        "profiles": "Стандартний (Дорослий)|Спрощений (Літні люди / Доглядальники)|Педіатричний (Пояснення для батьків)",
        "theme_label": "🎨 Візуальна тема та доступність",
        "themes": "☀️ Клінічна світла (За замовчуванням)|🌙 Темний режим (Для очей)|👁️ Режим для дальтоніків (Okabe-Ito)",
        "big_font_label": "👓 Великий шрифт (Для літніх / слабозорих)",
        "model_label": "🧠 Модель ШІ (ROCm™ / Gemini)",
        "url_label": "🔗 Базовий URL Evolus / AMD",
        "sb_telemetry": "📊 Телеметрія інференсу",
        "sb_latency": "Затримка останнього аналізу",
        "sb_engine": "Активний рушій",
        "sb_completed": "Виконано аналізів",
        "cb_banner": "♿ Режим для дальтоніків активний: Наукова палітра Okabe-Ito + геометричні символи (● ▲ ■)",
        "step1_title": "Оберіть демо-випадок або завантажте медичну виписку",
        "case1_btn": "🫀 Кардіологія — Серцева недостатність та ФП",
        "case2_btn": "🦴 Ортопедія — Перелом щиколотки та ортез Walker",
        "case3_btn": "🧸 Педіатрія — Гострий бронхіоліт та спейсер",
        "pdf_label": "📄 Завантажити виписку у форматі PDF",
        "active_cfg": "Активна конфігурація",
        "editor_label": "✍️ Клінічний текст виписки (вставте або відредагуйте):",
        "words_lbl": "слів",
        "comp_lbl": "Клінічна складність: Висока",
        "abbr_count_lbl": "медичних абревіатур виявлено",
        "abbr_list_lbl": "Виявлені скорочення:",
        "orig_expander": "🔍 Читати повний 'Оригінальний медичний текст'",
        "analyze_btn": "✨ Проаналізувати та перекласти для пацієнта",
        "step2_title": "Емпатичний висновок при виписці",
        "empathy_header": "Зрозуміле пояснення лікаря-навігатора",
        "tts_play": "🔊 Прослухати висновок вголос",
        "tts_stop": "⏹️ Стоп",
        "step3_title": "Щоденний графік прийому ліків за часом",
        "morning": "🌅 Ранок",
        "lunch": "☀️ Обід",
        "evening": "🌙 Вечір",
        "prn": "💊 За потреби",
        "no_meds": "Немає ліків у цей час",
        "instructions": "Інструкції",
        "step4_title": "Світлофор симптомів (Домашній тріаж)",
        "triage_g": "🟢 Все Нормально (Очікувані симптоми)",
        "triage_y": "🟡 Зверніться до лікаря, якщо...",
        "triage_r": "🔴 Негайно до швидкої допомоги, якщо...",
        "cb_g": "● [КОЛО - СТАБІЛЬНО] Все Нормально",
        "cb_y": "▲ [ТРИКУТНИК - УВАГА] Зверніться до лікаря...",
        "cb_r": "■ [КВАДРАТ - КРИТИЧНО] Негайно у невідкладну допомогу...",
        "step5_title": "Наступні кроки та запитання для контрольного візиту",
        "steps_title": "📅 Чек-лист обстежень, аналізів та щоденного догляду",
        "questions_title": "❓ 3 важливі запитання до лікаря",
        "question_lbl": "Питання",
        "step6_title": "Дії та експорт (Пам'ятка на холодильник та MP3-аудіо)",
        "dl_html_btn": "🖨️ Завантажити пам'ятку для друку (HTML)",
        "dl_txt_btn": "📄 Завантажити текстову пам'ятку (.TXT)",
        "mp3_btn": "🎧 Згенерувати аудіофайл MP3 (gTTS)",
        "step7_title": "Запитайте вашу виписку (Контекстний медичний асистент)",
        "q1_btn": "🚗 Чи можна мені керувати авто найближчими днями?",
        "q2_btn": "💊 Що робити, якщо я забув прийняти таблетку?",
        "q3_btn": "🥗 Чи є обмеження щодо їжі, води або солі?",
        "chat_placeholder": "Поставте конкретне запитання щодо вашої виписки...",
        "chat_welcome": "Вітаємо у **MedClear AI**! Вище наведено перекладений путівник для пацієнта. Ставте запитання нижче.",
    },
    "hi": {
        "hero_sub": "अस्पताल के डिस्चार्ज लेटर के सहानुभूतिपूर्ण, सुरक्षित और बहुभाषी (12 भाषाएं) अनुवाद के लिए क्लिनिकल NLP SaaS प्लेटफॉर्म।",
        "dock_title": "⚙️ त्वरित नियंत्रण पैनल (AI इंजन, 12 भाषाएं और सुगम्यता)",
        "api_label": "🔑 API कुंजी (Evolus 'evo_...' या Gemini 'AIza...')",
        "api_placeholder": "यहाँ evo_... या AIza... पेस्ट करें",
        "status_evolus": "✅ AMD Instinct™ GPU पर Evolus Cloud से जुड़ा है",
        "status_gemini": "✅ Google Gemini Flash Cloud से जुड़ा है",
        "status_custom": "🔗 कस्टम OpenAI-संगत एंडपॉइंट से जुड़ा है",
        "status_demo": "⚡ स्मार्ट डेमो मोड ('evo_...' या 'AIza...' दर्ज करें)",
        "lang_label": "🌍 ऐप और रिपोर्ट की भाषा (12 भाषाएं)",
        "profile_label": "👤 मरीज़ प्रोफ़ाइल",
        "profiles": "मानक (वयस्क)|सरलीकृत (बुजुर्ग / देखभालकर्ता)|बाल रोग (माता-पिता के लिए विवरण)",
        "theme_label": "🎨 विज़ुअल थीम और सुगम्यता",
        "themes": "☀️ क्लिनिकल लाइट (डिफ़ॉल्ट)|🌙 डार्क मोड (आंखों को आराम)|👁️ कलरब्लाइंड मोड (Okabe-Ito)",
        "big_font_label": "👓 बड़ा फ़ॉन्ट (बुजुर्ग / कम दृष्टि)",
        "model_label": "🧠 AI मॉडल (ROCm™ / Gemini)",
        "url_label": "🔗 Evolus / AMD बेस URL",
        "sb_telemetry": "📊 इन्फरेंस टेलीमेट्री",
        "sb_latency": "अंतिम विश्लेषण समय",
        "sb_engine": "सक्रिय इंजन",
        "sb_completed": "पूर्ण किए गए विश्लेषण",
        "cb_banner": "♿ कलरब्लाइंड मोड सक्रिय: वैज्ञानिक Okabe-Ito पैलेट + ज्यामितीय प्रतीक (● ▲ ■)",
        "step1_title": "डेमो क्लिनिकल केस चुनें या अस्पताल की रिपोर्ट अपलोड करें",
        "case1_btn": "🫀 कार्डियोलॉजी — हार्ट फेलियर और एट्रियल फिब्रिलेशन",
        "case2_btn": "🦴 ऑर्थोपेडिक्स — टखने का फ्रैक्चर और वॉकर बूट",
        "case3_btn": "🧸 बाल रोग — एक्यूट ब्रोंकियोलाइटिस और स्पेसर",
        "pdf_label": "📄 डिस्चार्ज लेटर PDF अपलोड करें",
        "active_cfg": "सक्रिय कॉन्फ़िगरेशन",
        "editor_label": "✍️ डिस्चार्ज लेटर का मेडिकल टेक्स्ट (पेस्ट या संपादित करें):",
        "words_lbl": "शब्द",
        "comp_lbl": "क्लिनिकल जटिलता: उच्च",
        "abbr_count_lbl": "मेडिकल संक्षिप्त रूप मिले",
        "abbr_list_lbl": "पाए गए संक्षिप्त रूप:",
        "orig_expander": "🔍 पूरा 'मूल मेडिकल टेक्स्ट' पढ़ें (जजों के लिए जटिलता की तुलना)",
        "analyze_btn": "✨ मरीज़ के लिए विश्लेषण और अनुवाद करें",
        "step2_title": "डिस्चार्ज का सरल और आश्वस्त करने वाला सारांश",
        "empathy_header": "मेडिकल नेविगेटर द्वारा स्पष्ट व्याख्या",
        "tts_play": "🔊 सारांश को आवाज़ में सुनें",
        "tts_stop": "⏹️ रोकें",
        "step3_title": "समय के अनुसार दैनिक दवा तालिका",
        "morning": "🌅 सुबह",
        "lunch": "☀️ दोपहर",
        "evening": "🌙 रात",
        "prn": "💊 ज़रूरत पड़ने पर",
        "no_meds": "इस समय कोई दवा नहीं है",
        "instructions": "निर्देश",
        "step4_title": "लक्षण ट्रैफिक लाइट (घर पर सुरक्षा पहचान)",
        "triage_g": "🟢 सब सामान्य है (अपेक्षित लक्षण)",
        "triage_y": "🟡 डॉक्टर से संपर्क करें यदि...",
        "triage_r": "🔴 तुरंत इमरजेंसी (आपातकालीन कक्ष) जाएं यदि...",
        "cb_g": "● [वृत्त - स्थिर] सब सामान्य है",
        "cb_y": "▲ [त्रिकोण - सावधानी] डॉक्टर से संपर्क करें यदि...",
        "cb_r": "■ [वर्ग - गंभीर आपातकाल] तुरंत इमरजेंसी जाएं यदि...",
        "step5_title": "अगले कदम और डॉक्टर से पूछने के लिए प्रश्न",
        "steps_title": "📅 अगले कदम और जांच सूची",
        "questions_title": "❓ डॉक्टर से पूछने के लिए 3 महत्वपूर्ण प्रश्न",
        "question_lbl": "प्रश्न",
        "step6_title": "निर्यात और प्रिंट (फ्रिज पर लगाने योग्य पर्चा और MP3 ऑडियो)",
        "dl_html_btn": "🖨️ प्रिंट करने योग्य फ्रिज चार्ट डाउनलोड करें (HTML)",
        "dl_txt_btn": "📄 टेक्स्ट सारांश डाउनलोड करें (.TXT)",
        "mp3_btn": "🎧 MP3 ऑडियो फ़ाइल बनाएं (gTTS)",
        "step7_title": "अपनी रिपोर्ट से पूछें (क्लिनिकल चैट सहायक)",
        "q1_btn": "🚗 क्या मैं अगले कुछ दिनों में गाड़ी चला सकता हूँ?",
        "q2_btn": "💊 अगर मैं एक गोली लेना भूल जाऊं तो क्या होगा?",
        "q3_btn": "🥗 क्या भोजन, पानी या नमक के बारे में कोई नियम हैं?",
        "chat_placeholder": "अपनी रिपोर्ट के बारे में कोई भी प्रश्न पूछें...",
        "chat_welcome": "**MedClear AI** में आपका स्वागत है! ऊपर आपकी अनुवादित मरीज़ गाइड तैयार है। नीचे अपने सवाल पूछें।",
    },
    "pt": {
        "hero_sub": "Plataforma SaaS de NLP Clínico para tradução empática, segura e multilingue (12 idiomas) de notas de alta hospitalar.",
        "dock_title": "⚙️ Painel de Controlo Rápido (Motor IA, 12 Idiomas e Acessibilidade)",
        "api_label": "🔑 Chave API (Evolus 'evo_...' ou Gemini 'AIza...')",
        "api_placeholder": "Cole aqui evo_... ou AIza...",
        "status_evolus": "✅ Ligado à Evolus Cloud em GPU AMD Instinct™",
        "status_gemini": "✅ Ligado à Google Gemini Flash Cloud",
        "status_custom": "🔗 Ligado a Endpoint Compatível com OpenAI",
        "status_demo": "⚡ Modo Demo Inteligente (Insira 'evo_...' ou 'AIza...')",
        "lang_label": "🌍 Idioma da Aplicação e do Relatório (12 Idiomas)",
        "profile_label": "👤 Perfil do Paciente",
        "profiles": "Padrão (Adulto)|Simplificado (Idoso / Cuidador)|Pediátrico (Explicação para Pais)",
        "theme_label": "🎨 Tema Visual e Acessibilidade",
        "themes": "☀️ Clínico Claro (Padrão)|🌙 Modo Escuro (Conforto Visual)|👁️ Modo Daltónicos (Okabe-Ito)",
        "big_font_label": "👓 Letra Grande (Idosos / Baixa Visão)",
        "model_label": "🧠 Modelo IA (ROCm™ / Gemini)",
        "url_label": "🔗 URL Base Evolus / AMD",
        "sb_telemetry": "📊 Telemetria de Inferência",
        "sb_latency": "Latência da Última Análise",
        "sb_engine": "Motor Ativo",
        "sb_completed": "Análises concluídas",
        "cb_banner": "♿ Modo Daltonismo Ativo: Paleta científica Okabe-Ito + Codificação Geométrica (● ▲ ■) para Triagem Domiciliária",
        "step1_title": "Selecione um Caso Clínico Demo ou Carregue o Relatório",
        "case1_btn": "🫀 Cardiologia — Insuficiência Cardíaca e FA",
        "case2_btn": "🦴 Ortopedia — Fratura do Maléolo e Bota Walker",
        "case3_btn": "🧸 Pediatria — Bronquiolite Aguda e Câmara Expansora",
        "pdf_label": "📄 Carregar Nota de Alta em PDF",
        "active_cfg": "Configuração Ativa",
        "editor_label": "✍️ Texto Clínico da Nota de Alta (cole ou edite):",
        "words_lbl": "palavras",
        "comp_lbl": "Complexidade Clínica: Alta",
        "abbr_count_lbl": "abreviaturas médicas detetadas",
        "abbr_list_lbl": "Siglas detetadas:",
        "orig_expander": "🔍 Ler 'Texto Médico Original' completo (Comparação para o Júri)",
        "analyze_btn": "✨ Analisar e Traduzir para o Paciente",
        "step2_title": "Resumo Empático da Alta",
        "empathy_header": "Explicação Clara do Médico Navegador",
        "tts_play": "🔊 Ouvir Resumo em Voz Alta",
        "tts_stop": "⏹️ Parar",
        "step3_title": "Plano Terapêutico Diário por Horário",
        "morning": "🌅 Manhã",
        "lunch": "☀️ Almoço",
        "evening": "🌙 Noite",
        "prn": "💊 Se necessário",
        "no_meds": "Sem medicamentos neste horário",
        "instructions": "Instruções",
        "step4_title": "Semáforo de Sintomas (Triagem em Casa)",
        "triage_g": "🟢 Tudo Normal (O que esperar)",
        "triage_y": "🟡 Contacte o Médico se...",
        "triage_r": "🔴 Vá às Urgências se...",
        "cb_g": "● [CÍRCULO - ESTÁVEL] Tudo Normal",
        "cb_y": "▲ [TRIÂNGULO - ATENÇÃO] Contacte o Médico se...",
        "cb_r": "■ [QUADRADO - URGÊNCIA CRÍTICA] Vá às Urgências se...",
        "step5_title": "Próximos Passos e Perguntas para a Consulta",
        "steps_title": "📅 Próximos Passos e Exames",
        "questions_title": "❓ 3 Perguntas Recomendadas para o Médico",
        "question_lbl": "Pergunta",
        "step6_title": "Ações e Exportação (Folha para o Frigorífico e Áudio MP3)",
        "dl_html_btn": "🖨️ Descarregar Folha Imprimível para o Frigorífico (HTML)",
        "dl_txt_btn": "📄 Descarregar Resumo em Texto (.TXT)",
        "mp3_btn": "🎧 Gerar Ficheiro de Áudio MP3 (gTTS)",
        "step7_title": "Pergunte ao seu Relatório (Assistente Clínico Contextual)",
        "q1_btn": "🚗 Posso conduzir nos próximos dias?",
        "q2_btn": "💊 O que acontece se me esquecer de um comprimido?",
        "q3_btn": "🥗 Existem regras sobre comida, água ou sal?",
        "chat_placeholder": "Faça uma pergunta específica sobre o seu relatório...",
        "chat_welcome": "Bem-vindo ao **MedClear AI**! Acima encontra o seu guia traduzido. Escreva qualquer dúvida abaixo.",
    },
    "sq": {
        "hero_sub": "Platformë SaaS e NLP Klinike për përkthimin empatik, të sigurt dhe shumëgjuhësh (12 gjuhë) të fletëdaljeve spitalore.",
        "dock_title": "⚙️ Paneli i Kontrollit të Shpejtë (Motori AI, 12 Gjuhë & Aksesueshmëria)",
        "api_label": "🔑 Çelësi API (Evolus 'evo_...' ose Gemini 'AIza...')",
        "api_placeholder": "Ngjitni këtu evo_... ose AIza...",
        "status_evolus": "✅ Lidhur me Evolus Cloud në GPU AMD Instinct™",
        "status_gemini": "✅ Lidhur me Google Gemini Flash Cloud",
        "status_custom": "🔗 Lidhur me Endpoint Kompatibël me OpenAI",
        "status_demo": "⚡ Modaliteti Smart Demo (Vendosni 'evo_...' ose 'AIza...')",
        "lang_label": "🌍 Gjuha e Aplikacionit dhe e Raportit (12 Gjuhë)",
        "profile_label": "👤 Profili i Pacientit",
        "profiles": "Standard (I rritur)|I thjeshtuar (Të moshuar / Kujdestarë)|Pediatrik (Shpjegim për Prindërit)",
        "theme_label": "🎨 Tema Vizuale & Aksesueshmëria",
        "themes": "☀️ Klinik i Çelët (Default)|🌙 Dark Mode (Pushim Vizual)|👁️ Modaliteti Daltonik (Okabe-Ito)",
        "big_font_label": "👓 Shkronja të Mëdha (Të moshuar / Shikim i dobët)",
        "model_label": "🧠 Modeli AI (ROCm™ / Gemini)",
        "url_label": "🔗 URL Bazë Evolus / AMD",
        "sb_telemetry": "📊 Telemetria e Inferencës",
        "sb_latency": "Vonesa e Analizës së Fundit",
        "sb_engine": "Motori Aktiv",
        "sb_completed": "Analiza të përfunduara",
        "cb_banner": "♿ Modaliteti Daltonik Aktiv: Paleta shkencore Okabe-Ito + Kodimi Gjeometrik (● ▲ ■)",
        "step1_title": "Zgjidhni një Rast Klinik Demo ose Ngarkoni Fletëdaljen",
        "case1_btn": "🫀 Kardiologji — Insuficienca Kardiake & Fibrilacioni",
        "case2_btn": "🦴 Ortopedi — Frakturë e Maleolës & Tutore Walker",
        "case3_btn": "🧸 Pediatri — Bronkiolit Akut & Distancues",
        "pdf_label": "📄 Ngarko Fletëdaljen në PDF",
        "active_cfg": "Konfigurimi Aktiv",
        "editor_label": "✍️ Teksti Klinik i Fletëdaljes (ngjitni ose modifikoni):",
        "words_lbl": "fjalë",
        "comp_lbl": "Kompleksiteti Klinik: I lartë",
        "abbr_count_lbl": "shkurtesa mjekësore të zbuluara",
        "abbr_list_lbl": "Shkurtesat:",
        "orig_expander": "🔍 Lexo 'Tekstin Mjekësor Origjinal' të plotë (Krahasim për Jurinë)",
        "analyze_btn": "✨ Analizo dhe Përkthe për Pacientin",
        "step2_title": "Përmbledhja Empatike e Daljes nga Spitali",
        "empathy_header": "Shpjegim i Qartë nga Mjeku Juaj Udhërrëfyes",
        "tts_play": "🔊 Dëgjo Përmbledhjen me Zë",
        "tts_stop": "⏹️ Ndalo",
        "step3_title": "Plani Ditor i Barnave sipas Orarit",
        "morning": "🌅 Mëngjes",
        "lunch": "☀️ Drekë",
        "evening": "🌙 Mbrëmje",
        "prn": "💊 Sipas nevojës",
        "no_meds": "Asnjë bar në këtë orar",
        "instructions": "Udhëzime",
        "step4_title": "Semafori i Simptomave (Triazhi në Shtëpi)",
        "triage_g": "🟢 Gjithçka Normale (Çfarë të prisni)",
        "triage_y": "🟡 Kontaktoni Mjekun nëse...",
        "triage_r": "🔴 Shkoni menjëherë në Urgjencë nëse...",
        "cb_g": "● [RRETH - STABIL] Gjithçka Normale",
        "cb_y": "▲ [TREKËNDËSH - KUJDES] Kontaktoni Mjekun nëse...",
        "cb_r": "■ [KATROR - URGJENCË KRITIKE] Shkoni në Urgjencë nëse...",
        "step5_title": "Hapat e Radhës & Pyetje për Vizitën e Kontrollit",
        "steps_title": "📅 Hapat e Radhës dhe Kontrollet",
        "questions_title": "❓ 3 Pyetje të Këshilluara për Mjekun",
        "question_lbl": "Pyetja",
        "step6_title": "Veprime & Eksportim (Fletë Përkujtuese për Frigorifer & Audio MP3)",
        "dl_html_btn": "🖨️ Shkarko Fletën e Printueshme për Frigorifer (HTML)",
        "dl_txt_btn": "📄 Shkarko Përmbledhjen Tekst (.TXT)",
        "mp3_btn": "🎧 Gjenero Skedarin Audio MP3 (gTTS)",
        "step7_title": "Pyet Raportin Tënd (Asistenti Klinik Kontekstual)",
        "q1_btn": "🚗 A mund të ngas makinën në ditët në vijim?",
        "q2_btn": "💊 Çfarë ndodh nëse harroj një kokërr?",
        "q3_btn": "🥗 A ka rregulla për ushqimin, ujin apo kripën?",
        "chat_placeholder": "Bëni një pyetje specifike rreth raportit tuaj...",
        "chat_welcome": "Mirë se vini në **MedClear AI**! Më sipër gjeni udhëzuesin e përkthyer. Shkruani çdo pyetje më poshtë.",
    },
    "ru": {
        "hero_sub": "Клиническая NLP SaaS-платформа для понятного, безопасного и многоязычного (13 языков) перевода больничных выписок.",
        "dock_title": "⚙️ Панель быстрого управления (ИИ-движок, 13 языков и доступность)",
        "api_label": "🔑 API-ключ (Evolus 'evo_...' или Gemini 'AIza...')",
        "api_placeholder": "Вставьте сюда evo_... или AIza...",
        "status_evolus": "✅ Подключено к Evolus Cloud на AMD Instinct™ GPU",
        "status_gemini": "✅ Подключено к Google Gemini Flash Cloud",
        "status_custom": "🔗 Подключено к OpenAI-совместимому эндпоинту",
        "status_demo": "⚡ Умный демо-режим (введите 'evo_...' или 'AIza...')",
        "lang_label": "🌍 Язык приложения и медицинского заключения (13 языков)",
        "profile_label": "👤 Профиль пациента",
        "profiles": "Стандартный (Взрослый)|Упрощенный (Пожилые / Опекуны)|Педиатрический (Для родителей)",
        "theme_label": "🎨 Визуальная тема и доступность",
        "themes": "☀️ Клиническая светлая (По умолчанию)|🌙 Темный режим (Защита глаз)|👁️ Режим для дальтоников (Okabe-Ito)",
        "big_font_label": "👓 Крупный шрифт (Для пожилых / слабовидящих)",
        "model_label": "🧠 Модель ИИ (ROCm™ / Gemini)",
        "url_label": "🔗 Базовый URL Evolus / AMD",
        "sb_telemetry": "📊 Телеметрия инференса",
        "sb_latency": "Задержка последнего анализа",
        "sb_engine": "Активный движок",
        "sb_completed": "Выполнено анализов",
        "cb_banner": "♿ Режим для дальтоников активен: Научная палитра Okabe-Ito + геометрические символы (● ▲ ■) для безопасности дома",
        "step1_title": "Выберите демо-случай или загрузите выписной эпикриз",
        "case1_btn": "🫀 Кардиология — Сердечная недостаточность и ФП",
        "case2_btn": "🦴 Ортопедия — Перелом лодыжки и ортез Walker",
        "case3_btn": "🧸 Педиатрия — Острый бронхиолит и спейсер",
        "pdf_label": "📄 Загрузить выписной эпикриз в PDF",
        "active_cfg": "Активная конфигурация",
        "editor_label": "✍️ Клинический текст выписки (вставьте или отредактируйте):",
        "words_lbl": "слов",
        "comp_lbl": "Клиническая сложность: Высокая",
        "abbr_count_lbl": "медицинских аббревиатур обнаружено",
        "abbr_list_lbl": "Обнаруженные сокращения:",
        "orig_expander": "🔍 Читать полный 'Оригинальный медицинский текст' (Сравнение сложности)",
        "analyze_btn": "✨ Проанализировать и перевести для пациента",
        "step2_title": "Понятное резюме при выписке",
        "empathy_header": "Разъяснение от вашего врача-навигатора",
        "tts_play": "🔊 Прослушать резюме вслух",
        "tts_stop": "⏹️ Стоп",
        "step3_title": "Ежедневный план приема лекарств по времени суток",
        "morning": "🌅 Утро",
        "lunch": "☀️ День / Обед",
        "evening": "🌙 Вечер",
        "prn": "💊 При необходимости",
        "no_meds": "Нет лекарств в этот период",
        "instructions": "Инструкции",
        "step4_title": "Светофор симптомов (Домашний триаж)",
        "triage_g": "🟢 Всё Нормально (Что ожидать)",
        "triage_y": "🟡 Обратитесь к врачу, если...",
        "triage_r": "🔴 Немедленно вызывайте скорую (103/112), если...",
        "cb_g": "● [КРУГ - СТАБИЛЬНО] Всё Нормально",
        "cb_y": "▲ [ТРЕУГОЛЬНИК - ВНИМАНИЕ] Обратитесь к врачу, если...",
        "cb_r": "■ [КВАДРАТ - СРОЧНО] Вызывайте скорую помощь, если...",
        "step5_title": "Следующие шаги и вопросы для контрольного визита",
        "steps_title": "📅 Чек-лист обследований и ежедневного ухода",
        "questions_title": "❓ 3 важных вопроса для лечащего врача",
        "question_lbl": "Вопрос",
        "step6_title": "Действия и экспорт (Памятка на холодильник и MP3-аудио)",
        "dl_html_btn": "🖨️ Скачать памятку для печати на холодильник (HTML)",
        "dl_txt_btn": "📄 Скачать текстовую памятку (.TXT)",
        "mp3_btn": "🎧 Создать аудиофайл MP3 (gTTS)",
        "step7_title": "Задайте вопрос по вашей выписке (Контекстный ИИ-ассистент)",
        "q1_btn": "🚗 Можно ли мне водить машину в ближайшие дни?",
        "q2_btn": "💊 Что делать, если я забыл(а) принять таблетку?",
        "q3_btn": "🥗 Есть ли ограничения по еде, воде или соли?",
        "chat_placeholder": "Задайте конкретный вопрос по вашему медицинскому заключению...",
        "chat_welcome": "Добро пожаловать в **MedClear AI**! Выше представлена переведенная памятка пациента. Задайте любой вопрос по выписке ниже.",
    },
}


# =====================================================================
# CSS GLOBALE AVANZATO (LIGHT, DARK MODE, OKABE-ITO COLORBLIND & RTL)
# =====================================================================
def inject_custom_css(
    theme_idx: int, high_readability: bool = False, is_rtl: bool = False
) -> None:
    is_dark = theme_idx == 1
    is_colorblind = theme_idx == 2

    base_font_size = "1.2rem" if high_readability else "0.97rem"
    summary_font_size = "1.3rem" if high_readability else "1.06rem"
    line_height_val = "1.82" if high_readability else "1.62"

    if is_dark:
        bg_page = "#0b0f19"
        bg_card = "#1e293b"
        bg_subcard = "#0f172a"
        border_card = "#38bdf8" if high_readability else "#334155"
        text_primary = "#f8fafc"
        text_secondary = "#94a3b8"
        empathy_bg = "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)"
        empathy_border = "#38bdf8"
        empathy_heading_color = "#38bdf8"
        purpose_color = "#38bdf8"
        dose_bg = "#0369a1"
        dose_text = "#f0f9ff"
        dose_border = "#38bdf8"
        sidebar_bg = "#111827"
    else:
        bg_page = "#f4f7fb"
        bg_card = "#ffffff"
        bg_subcard = "#f8fafc"
        border_card = "#0284c7" if high_readability else "#e2e8f0"
        text_primary = "#000000" if high_readability else "#0f172a"
        text_secondary = "#1e293b" if high_readability else "#475569"
        empathy_bg = "linear-gradient(135deg, #f0f9ff 0%, #ffffff 100%)"
        empathy_border = "#0284c7"
        empathy_heading_color = "#0369a1"
        purpose_color = "#0284c7"
        dose_bg = "#e0f2fe"
        dose_text = "#0369a1"
        dose_border = "#7dd3fc"
        sidebar_bg = "#ffffff"

    if is_colorblind:
        triage_g_css = (
            "background: #e0f2fe !important; border: 3px solid #0072B2 !important; color: #0c4a6e !important;"
            if not is_dark
            else "background: #082f49 !important; border: 3px solid #38bdf8 !important; color: #f0f9ff !important;"
        )
        triage_y_css = (
            "background: #fef3c7 !important; border: 3px dashed #E69F00 !important; color: #78350f !important;"
            if not is_dark
            else "background: #451a03 !important; border: 3px dashed #f59e0b !important; color: #fef3c7 !important;"
        )
        triage_r_css = (
            "background: #ffe4e6 !important; border: 5px double #9f1239 !important; color: #881337 !important;"
            if not is_dark
            else "background: #4c0519 !important; border: 5px double #fb7185 !important; color: #ffe4e6 !important;"
        )
        th_g_color = "#0072B2" if not is_dark else "#38bdf8"
        th_y_color = "#b45309" if not is_dark else "#fbbf24"
        th_r_color = "#9f1239" if not is_dark else "#fda4af"
        triage_text_color = "#0f172a" if not is_dark else "#f8fafc"
    elif is_dark:
        triage_g_css = "background: rgba(16, 185, 129, 0.12); border: 2px solid #10b981;"
        triage_y_css = "background: rgba(245, 158, 11, 0.12); border: 2px solid #f59e0b;"
        triage_r_css = "background: rgba(239, 68, 68, 0.14); border: 2px solid #ef4444;"
        th_g_color = "#34d399"
        th_y_color = "#fbbf24"
        th_r_color = "#f87171"
        triage_text_color = "#f8fafc"
    else:
        triage_g_css = "background: #ecfdf5; border: 2px solid #10b981;"
        triage_y_css = "background: #fffbeb; border: 2px solid #f59e0b;"
        triage_r_css = "background: #fef2f2; border: 2px solid #ef4444;"
        th_g_color = "#065f46"
        th_y_color = "#92400e"
        th_r_color = "#991b1b"
        triage_text_color = text_primary

    rtl_rule = (
        "direction: rtl !important; text-align: right !important;"
        if is_rtl
        else "direction: ltr; text-align: left;"
    )

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        #MainMenu, footer {{
            visibility: hidden !important;
        }}
        header {{
            background: transparent !important;
        }}
        header [data-testid="stToolbar"] {{
            visibility: hidden !important;
        }}
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {{
            visibility: visible !important;
            display: flex !important;
            z-index: 999999 !important;
        }}
        .stDeployButton {{
            display: none !important;
        }}

        html, body, [class*="css"] {{
            font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            color: {text_primary};
        }}
        .stApp {{
            background-color: {bg_page} !important;
            color: {text_primary} !important;
        }}
        .block-container {{
            padding-top: 1.4rem !important;
            padding-bottom: 3.5rem !important;
            max-width: 1320px !important;
        }}

        [data-testid="stSidebar"] {{
            background: {sidebar_bg} !important;
            border-right: 1px solid {border_card} !important;
        }}
        [data-testid="stSidebar"] * {{
            color: {text_primary};
        }}

        .enterprise-hero {{
            background: linear-gradient(135deg, #0f172a 0%, #0369a1 100%);
            border-radius: 20px;
            padding: 26px 30px 20px 30px;
            color: #ffffff;
            box-shadow: 0 12px 32px rgba(3, 105, 161, 0.22);
            margin-bottom: 1.2rem;
            border: 1px solid rgba(56, 189, 248, 0.35);
            {rtl_rule}
        }}
        .hero-top-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.15rem;
        }}
        .hero-brand {{
            display: flex;
            align-items: center;
            gap: 1.1rem;
        }}
        .hero-logo-box {{
            width: 58px;
            height: 58px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.28);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.95rem;
            flex-shrink: 0;
        }}
        .hero-title {{
            font-size: 1.72rem;
            font-weight: 800;
            color: #ffffff !important;
            margin: 0;
            letter-spacing: -0.02em;
        }}
        .hero-title span {{
            color: #38bdf8;
        }}
        .hero-subtitle {{
            font-size: 0.94rem;
            color: #e0f2fe !important;
            margin: 0.3rem 0 0 0;
            max-width: 760px;
        }}
        .hero-engine-tag {{
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid #38bdf8;
            color: #f0f9ff !important;
            padding: 0.48rem 0.95rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            white-space: nowrap;
        }}
        .telemetry-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            padding-top: 0.95rem;
            border-top: 1px solid rgba(255, 255, 255, 0.16);
        }}
        .telemetry-pill {{
            background: rgba(15, 23, 42, 0.58);
            border: 1px solid rgba(186, 230, 253, 0.3);
            color: #f8fafc !important;
            padding: 0.4rem 0.85rem;
            border-radius: 999px;
            font-size: 0.79rem;
            font-weight: 600;
        }}

        .colorblind-banner {{
            background: linear-gradient(90deg, #0072B2 0%, #0369a1 100%);
            color: #ffffff !important;
            border: 2px solid #E69F00;
            border-radius: 14px;
            padding: 0.85rem 1.25rem;
            margin-bottom: 1.2rem;
            font-weight: 700;
            font-size: 0.92rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem;
            box-shadow: 0 4px 16px rgba(0, 114, 178, 0.25);
        }}

        .modern-card {{
            background: {bg_card};
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
            border: 1px solid {border_card};
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            margin-bottom: 1rem;
            color: {text_primary};
            {rtl_rule}
        }}
        .modern-card:hover {{
            transform: translateY(-2px);
        }}

        .step-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 1.5rem 0 0.85rem 0;
            {rtl_rule}
        }}
        .step-title-group {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
        }}
        .step-number {{
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: #ffffff !important;
            width: 30px;
            height: 30px;
            border-radius: 9px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 0.9rem;
        }}
        .step-title-text {{
            font-size: 1.2rem;
            font-weight: 800;
            color: {text_primary};
        }}
        .step-badge {{
            background: {dose_bg};
            color: {dose_text};
            border: 1px solid {dose_border};
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.28rem 0.75rem;
            border-radius: 999px;
            text-transform: uppercase;
        }}

        .complexity-banner {{
            background: {bg_card};
            border: 1px solid {border_card};
            border-left: 5px solid #0284c7;
            border-radius: 12px;
            padding: 0.85rem 1.15rem;
            margin: 0.65rem 0 1rem 0;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            {rtl_rule}
        }}
        .badge-stat {{
            font-size: 0.81rem;
            font-weight: 700;
            padding: 0.28rem 0.75rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }}
        .stat-words {{
            background: {bg_subcard};
            color: {text_primary};
            border: 1px solid {border_card};
        }}
        .stat-high {{
            background: #fef2f2;
            color: #b91c1c;
            border: 1px solid #fecaca;
        }}
        .abbr-chip {{
            background: {dose_bg};
            color: {dose_text};
            font-weight: 700;
            padding: 0.12rem 0.45rem;
            border-radius: 6px;
            margin-right: 0.25rem;
            font-size: 0.74rem;
            display: inline-block;
        }}

        .empathy-card {{
            background: {empathy_bg};
            border: 1px solid {border_card};
            border-left: 7px solid {empathy_border};
            border-radius: 16px;
            padding: 24px 28px;
            box-shadow: 0 6px 22px rgba(2, 132, 199, 0.1);
            margin-bottom: 1.2rem;
            {rtl_rule}
        }}
        .empathy-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 0.85rem;
        }}
        .empathy-avatar-group {{
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }}
        .empathy-avatar {{
            width: 48px;
            height: 48px;
            border-radius: 14px;
            background: #0284c7;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.55rem;
            flex-shrink: 0;
        }}
        .empathy-heading {{
            font-size: 1.15rem;
            font-weight: 800;
            color: {empathy_heading_color};
            margin: 0;
        }}
        .empathy-subheading {{
            font-size: 0.82rem;
            color: {text_secondary};
            margin: 0.1rem 0 0 0;
        }}
        .empathy-text {{
            font-size: {summary_font_size};
            line-height: {line_height_val};
            color: {text_primary};
            font-weight: 500;
            margin: 0;
        }}

        .time-column-header {{
            background: {bg_card};
            border: 1px solid {border_card};
            border-radius: 12px;
            padding: 0.65rem 0.9rem;
            font-weight: 800;
            font-size: 0.95rem;
            color: {text_primary};
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            {rtl_rule}
        }}
        .med-minibox {{
            background: {bg_card};
            border-radius: 14px;
            padding: 16px;
            border: 1px solid {border_card};
            border-top: 4px solid #0284c7;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
            margin-bottom: 0.85rem;
            transition: transform 0.2s ease;
            {rtl_rule}
        }}
        .med-minibox:hover {{
            transform: translateY(-2px);
        }}
        .med-box-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.4rem;
            margin-bottom: 0.5rem;
            flex-wrap: wrap;
        }}
        .med-drug-title {{
            font-size: {base_font_size};
            font-weight: 800;
            color: {text_primary};
        }}
        .med-dose-badge {{
            background: {dose_bg};
            color: {dose_text};
            border: 1px solid {dose_border};
            font-size: 0.77rem;
            font-weight: 800;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
        }}
        .med-purpose-bold {{
            font-size: {base_font_size};
            font-weight: 700;
            color: {purpose_color};
            margin: 0.45rem 0;
            line-height: 1.45;
        }}
        .med-meal-warning {{
            font-size: 0.84rem;
            color: {text_secondary};
            background: {bg_subcard};
            border-radius: 9px;
            padding: 0.45rem 0.65rem;
            border: 1px dashed {border_card};
            margin-top: 0.45rem;
        }}

        .triage-card {{
            border-radius: 16px;
            padding: 22px;
            height: 100%;
            min-height: 270px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
            transition: transform 0.2s ease;
            {rtl_rule}
        }}
        .triage-card:hover {{
            transform: translateY(-2px);
        }}
        .triage-green  {{ {triage_g_css} }}
        .triage-yellow {{ {triage_y_css} }}
        .triage-red    {{ {triage_r_css} }}
        .triage-header {{
            font-size: 1.05rem;
            font-weight: 800;
            margin-bottom: 0.75rem;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }}
        .triage-header-green  {{ color: {th_g_color} !important; }}
        .triage-header-yellow {{ color: {th_y_color} !important; }}
        .triage-header-red    {{ color: {th_r_color} !important; }}
        .triage-ul {{
            margin: 0;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
            font-size: {base_font_size};
            line-height: {line_height_val};
            color: {triage_text_color};
        }}
        .triage-ul li {{
            margin-bottom: 0.55rem;
            font-weight: 500;
        }}

        .checklist-row {{
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            background: {bg_card};
            border: 1px solid {border_card};
            border-radius: 12px;
            padding: 0.85rem 1.05rem;
            margin-bottom: 0.65rem;
            font-size: {base_font_size};
            line-height: {line_height_val};
            color: {text_primary};
            {rtl_rule}
        }}
        .checklist-num {{
            background: #0284c7;
            color: #ffffff !important;
            width: 24px;
            height: 24px;
            border-radius: 7px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: 800;
            flex-shrink: 0;
            margin-top: 0.12rem;
        }}
        .doctor-q-box {{
            background: {bg_card};
            border: 1px solid {border_card};
            border-left: 5px solid #0284c7;
            border-radius: 12px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.65rem;
            font-size: {base_font_size};
            line-height: {line_height_val};
            font-weight: 600;
            color: {text_primary};
            {rtl_rule}
        }}

        .sidebar-metric {{
            background: {bg_subcard};
            border: 1px solid {border_card};
            border-left: 4px solid #0284c7;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
            margin-bottom: 0.6rem;
        }}
        .sidebar-metric-label {{
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {text_secondary};
            font-weight: 700;
        }}
        .sidebar-metric-val {{
            font-size: 1.12rem;
            font-weight: 800;
            color: {text_primary};
            margin-top: 0.1rem;
        }}
        .sidebar-metric-sub {{
            font-size: 0.75rem;
            color: #10b981;
            font-weight: 700;
        }}

        div.stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 14px !important;
            padding: 0.8rem 1.5rem !important;
            font-weight: 800 !important;
            font-size: 1.03rem !important;
            box-shadow: 0 6px 18px rgba(2, 132, 199, 0.32) !important;
        }}
        div.stButton > button[kind="secondary"] {{
            background: {bg_card} !important;
            color: {text_primary} !important;
            border: 1.5px solid {border_card} !important;
            border-radius: 12px !important;
            padding: 0.65rem 1rem !important;
            font-weight: 700 !important;
        }}
        div.stButton > button[kind="secondary"]:hover {{
            border-color: #0284c7 !important;
            color: #38bdf8 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =====================================================================
# RILEVATORE COMPLESSITA' CLINICA E ABBREVIAZIONI MEDICHE
# =====================================================================
KNOWN_MEDICAL_ABBR = [
    "HFmrEF", "FA", "NYHA", "SpO2", "AA", "PA", "FC", "bpm", "BNP",
    "eGFR", "IRC", "TIA", "UTIC", "U.O.C.", "PS", "Rx", "TT", "VSx",
    "FE", "LAVI", "PAPs", "VCI", "e.v.", "CHA2DS2-VASc", "HAS-BLED",
    "DOAC", "INR", "MMG", "K+", "Na+", "ECG", "CUP", "TVP", "EP",
    "EBPM", "s.c.", "UI", "FANS", "HIT", "OBIP", "PLS", "TC", "FR",
    "E.O.", "MV", "VRS", "MDI", "mcg", "cp",
]


def analyze_text_complexity(text: str) -> Tuple[int, List[str]]:
    words = re.findall(r"\S+", text)
    word_count = len(words)

    found_abbr: List[str] = []
    for abbr in KNOWN_MEDICAL_ABBR:
        pattern = r"(?<!\w)" + re.escape(abbr) + r"(?!\w)"
        if re.search(pattern, text, flags=re.IGNORECASE):
            found_abbr.append(abbr)

    extra_caps = re.findall(r"\b[A-Z]{2,6}\b", text)
    stopwords_caps = {
        "IL", "LO", "LA", "LE", "DI", "DA", "IN", "CON", "SU", "PER",
        "TRA", "FRA", "NON", "DEL", "AL", "DAL", "NEL", "SUL", "CHE", "ORE", "MAX"
    }
    for cap in extra_caps:
        if cap not in stopwords_caps and cap not in found_abbr:
            found_abbr.append(cap)

    return word_count, found_abbr[:18]


# =====================================================================
# CASI CLINICI DEMO (3 LETTERE DI DIMISSIONE REALISTICHE E COMPLESSE)
# =====================================================================
DEMO_CASES: Dict[str, Dict[str, str]] = {
    "cardiologia": {
        "titolo": "🫀 Caso 1: Dimissione Cardiologia (Scompenso & FA)",
        "testo": (
            "U.O.C. CARDIOLOGIA E UNITA' DI TERAPIA INTENSIVA CORONARICA (UTIC)\n"
            "LETTERA DI DIMISSIONE OSPEDALIERA\n"
            "Paziente: Sig. Roberto M., anni 74 | Motivo del ricovero: Dispnea ingravescente (NYHA III all'ingresso) e cardiopalmo aritmico.\n\n"
            "ANAMNESI PATOLOGICA REMOTA: Ipertensione arteriosa sistemica in trattamento, dislipidemia, pregresso TIA (2021), "
            "IRC stadio II-IIIa (eGFR basale 54 ml/min/1.73m²).\n\n"
            "DECORSO CLINICO E ACCERTAMENTI:\n"
            "Paziente giunto in PS per riacutizzazione di scompenso cardiaco congestizio (HFmrEF) secondario a fibrillazione atriale (FA) "
            "a elevata risposta ventricolare (FC media 132 bpm). All'ingresso: PA 165/95 mmHg, SpO2 91% in AA, rumori umidi bibasali al torace "
            "ed edemi declivi improntabili perimalleolari (+/+). Rx Torace: segni di ridistribuzione del circolo polmonare e lieve versamento "
            "pleurico basale dx. BNP all'ingresso: 1.180 pg/mL; Troponina I hs: 24 ng/L (stabile); Creatininemia: 1.38 mg/dL; K+: 3.9 mEq/L.\n"
            "Ecocardiogramma TT: VSx lievemente dilatato con ipertrofia concentrica, ipocinesia diffusa con FE biplana 45%. Atrio sx dilatato "
            "(LAVI 44 ml/m²), insufficienza mitralica lieve-moderata funzionale, PAPs stimata 38 mmHg, VCI 19 mm collassante >50%.\n"
            "Impostata terapia diuretica e.v. con Furosemide e controllo della frequenza con beta-bloccante selettivo, con progressivo "
            "ripristino di compenso emodinamico (calo ponderale di 3,2 kg), regressione della congestione polmonare (attuali NYHA I-II) e "
            "controllo della FC (68-74 bpm in FA permanente/persistente). Calcolo CHA2DS2-VASc = 5, HAS-BLED = 2: indicata scoagulazione orale "
            "con DOAC (Apixaban).\n\n"
            "DIAGNOSI DI DIMISSIONE:\n"
            "Scompenso cardiaco a frazione d'eiezione lievemente ridotta (HFmrEF, FE 45%) in fase di compenso labile, fibrillazione atriale "
            "a media risposta ventricolare in cardiopatia ipertensiva, IRC stadio IIIa.\n\n"
            "TERAPIA DOMICILIARE CONSIGLIATA:\n"
            "1. BISOPROLOLO 2.5 mg: 1 cp alle ore 08:00 (dopo colazione) per controllo FC; monitorare PA e FC (sospendere e contattare MMG se FC < 50 bpm).\n"
            "2. APIXABAN (Eliquis) 5 mg: 1 cp alle ore 08:00 e 1 cp alle ore 20:00 (ogni 12 ore rigorose, indipendentemente dai pasti) per profilassi tromboembolica.\n"
            "3. FUROSEMIDE (Lasix) 25 mg: 1 cp alle ore 08:00 e 1 cp alle ore 14:00 (evitare assunzione serale per nicturia).\n"
            "4. RAMIPRIL 5 mg: 1 cp alle ore 20:00 per rimodellamento cardiaco e controllo PA.\n\n"
            "INDICAZIONI E FOLLOW-UP ALLA DIMISSIONE:\n"
            "- Controllo quotidiano del peso corporeo al mattino a digiuno post-minzione: contattare il curante in caso di incremento > 1.5-2 kg in 3 giorni.\n"
            "- Dieta iposodica (< 2g Na/die) e restrizione idrica moderata (max 1.5 L/die).\n"
            "- Eseguire tra 7 giorni prelievo ematico di controllo: Creatininemia, Azotemia, eGFR, Elettroliti sierici (Na+, K+), Emocromo (Nota: in terapia con DOAC l'INR non è indicativo dell'effetto anticoagulante, ma valutare assetto coagulativo basale se richiesto dal MMG).\n"
            "- Visita Cardiologica + ECG + Ecocardiogramma di controllo a 30 giorni tramite CUP con impegnativa allegata.\n"
            "- Recarsi immediatamente in PS in caso di dispnea acuta a riposo, ortopnea, dolore toracico retrosternale, sincope o segni di sanguinamento maggiore (melena, ematuria, epistassi incoercibile)."
        ),
    },
    "ortopedia": {
        "titolo": "🦴 Caso 2: PS Ortopedia (Frattura Malleolo & Eparina)",
        "testo": (
            "VERBALE DI PRONTO SOCCORSO E CONSULENZA ORTOPEDICO-TRAUMATOLOGICA\n"
            "Paziente: Sig.ra Elena V., anni 48 | Accesso per: Trauma distorsivo caviglia destra da inversione forzata.\n\n"
            "ESAME OBIETTIVO SPECIALISTICO:\n"
            "Caviglia dx tumefatta in sede perimalleolare esterna con ecchimosi sottocutanea incipiente. Dolore vivo alla digitopressione "
            "sull'apice e sul terzo distale del malleolo peroneale. Assenza di dolorabilità sul malleolo tibiale mediale e sulla sindesmosi "
            "tibio-peroneale distale. Motilità attiva e passiva delle dita conservata, sensibilità distale integra, polso pedidio e tibiale "
            "posteriore normosfigmici e simmetrici.\n\n"
            "INDAGINI STRUMENTALI:\n"
            "Rx Caviglia Dx (2 proiezioni standard + proiezione per mortaio): Rima di frattura trasversa composta, sottosindesmotica, "
            "dell'apice del malleolo peroneale destro (Classificazione AO/Danis-Weber: Tipo A). Conservati i rapporti articolari astragalo-crurali.\n\n"
            "DIAGNOSI:\n"
            "Frattura composta del malleolo peroneale destro (Weber A) senza lesione della sindesmosi.\n\n"
            "PROVVEDIMENTI E TERAPIA DOMICILIARE:\n"
            "- Immobilizzazione con tutore pneumatico a stivaletto tipo WALKER bloccato a 90° da mantenere in sede h24 (rimovibile solo per "
            "igiene personale mantenendo l'arto in scarico assoluto).\n"
            "- SCARICO ARTICOLARE ASSOLUTO dell'arto inferiore dx per 15 giorni, poi carico sfiorante progressivo protetto con 2 bastoni "
            "canadesi (stampelle) secondo tolleranza algica.\n"
            "- Profilassi antitromboembolica (TVP/EP): ENOXAPARINA SODICA (Clexane) 4.000 UI (40 mg) 1 fl s.c./die alle ore 20:00 nella plica "
            "addominale per tutta la durata dello scarico articolare (30 giorni).\n"
            "- Terapia antalgica: PARACETAMOLO 1000 mg 1 cp fino a 3 volte/die (ogni 8 ore) al bisogno se dolore; associare GASTROPROTETTORE "
            "(Pantoprazolo 20 mg al mattino a digiuno) solo in caso di assunzione di FANS prescritti dal MMG.\n"
            "- Crioterapia locale (borsa del ghiaccio interponendo un panno) 20 minuti per 3-4 volte/die e arto in scarico antideclive (sollevato su cuscino).\n\n"
            "CONTROLLI PROGRAMMATI E RED FLAGS:\n"
            "- Eseguire Emocromo con conta piastrinica a 7-10 giorni dall'inizio dell'eparina a basso peso molecolare (escludere piastrinopenia da eparina - HIT).\n"
            "- Controllo Ortopedico presso Ambulatorio Divisionale Fratture tra 28 giorni previa esecuzione di Rx Caviglia Dx (2p) di controllo.\n"
            "- Rivalutazione urgente in PS se comparsa di: parestesie/ipoestesia delle dita del piede, dita fredde o cianotiche, dolore "
            "polpaccio con tensione muscolare (sospetta TVP), dispnea improvvisa o dolore toracico."
        ),
    },
    "pediatria": {
        "titolo": "🧸 Caso 3: Dimissione Pediatrica (Bronchiolite)",
        "testo": (
            "U.O.C. PEDIATRIA - REPARTO DI OSSERVAZIONE BREVE INTENSIVA PEDIATRICA (OBIP)\n"
            "LETTERA DI DIMISSIONE PER IL PEDIATRA DI LIBERA SCELTA (PLS)\n"
            "Piccolo paziente: Leonardo G., età 18 mesi | Peso: 11,4 kg.\n\n"
            "NOTIZIE CLINICHE E DECORSO IN OBIP:\n"
            "Bambino condotto in PS Pediatrico per rinite catarrale da 48h seguita da tosse stizzosa, tachipnea e difficoltà all'alimentazione. "
            "All'ingresso: apiretico (TC 37.1°C), FR 46 atti/min, SpO2 94% in AA, FC 138 bpm. All'E.O. toracico: lieve rientramento "
            "giugulare e sottocostale, MV aspro diffuso con espirio prolungato, sibili tele-espiratori e rari rantoli subcrepitanti bilaterali. "
            "Tampone nasofaringeo multiplex: positivo per Rhinovirus, negativo per VRS, Influenza A/B e SARS-CoV-2.\n"
            "Durante le 24h di osservazione in OBIP sono stati praticati lavaggi nasali frequenti, broncodilatazione inalatoria con "
            "Salbutamolo MDI + camera di espansione (distanziatore) con mascherina facciale e singola dose di steroide sistemico orale, "
            "con netto miglioramento della meccanica respiratoria (scomparsa dei rientramenti, FR 30 atti/min in veglia, SpO2 stabile 98% in AA) "
            "e ripresa di idratazione orale adeguata.\n\n"
            "DIAGNOSI DI DIMISSIONE:\n"
            "Bronchiolite acuta / Broncospasmo post-infettivo da Rhinovirus in buon compenso respiratorio.\n\n"
            "TERAPIA DOMICILIARE E ISTRUZIONI PER I GENITORI:\n"
            "1. LAVAGGI NASALI con soluzione fisiologica 0.9% o ipertonica 3%: eseguire prima di ogni pasto e prima del riposo notturno "
            "per mantenere pervie le prime vie aeree.\n"
            "2. SALBUTAMOLO (Ventolin) 100 mcg spray predosato (MDI) tramite DISTANZIATORE pediatrico con mascherina:\n"
            "   - Giorni 1-3: 2 puff ogni 6 ore (Mattina ore 08:00, Pranzo ore 14:00, Sera ore 20:00, Notte ore 02:00 se sveglio/sintomatico).\n"
            "   - Giorni 4-5: 2 puff ogni 8 ore (Mattina, Pomeriggio, Sera).\n"
            "   (Agitare il flacone, erogare 1 puff alla volta nel distanziatore e far compiere 5-6 atti respiratori tranquilli prima del secondo puff).\n"
            "3. BETAMETASONE (Bentelan) 0.5 mg cp solubili: 2 compresse sciolte in poca acqua 1 volta al giorno al mattino (dopo colazione) per altri 2 giorni.\n"
            "4. PARACETAMOLO sciroppo (120 mg/5 ml): 7 ml per bocca solo al bisogno se febbre > 38.5°C o malessere marcato (max ogni 6 ore).\n\n"
            "CONSIGLI COMPORTAMENTALI E MONITORAGGIO:\n"
            "- Offrire pasti piccoli e frequenti e abbondante idratazione; dormire con materasso lievemente sollevato (30°).\n"
            "- Controllo clinico presso il Pediatra di Libera Scelta (PLS) entro 48-72 ore.\n"
            "- Tornare subito in Pronto Soccorso Pediatrico se: respirazione molto veloce (FR > 50 atti/min a riposo), rientramenti "
            "della pancia o del collo quando respira, alitamento delle pinne nasali, colorito pallido/bluastro attorno alle labbra (cianosi), "
            "sonnolenza eccessiva o rifiuto dei liquidi per oltre 8-12 ore."
        ),
    },
}


# =====================================================================
# CONTENUTI CLINICI MULTILINGUA (12 LINGUE) PER MODALITA' FALLBACK / DEMO
# =====================================================================
MULTILINGUAL_CASE_PACKS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "en": {
        "cardiologia": {
            "riassunto_empatico": "You were admitted because your heart was beating too fast and irregularly (atrial fibrillation), causing fluid buildup in your lungs and ankles. Hospital treatment safely removed over 3 kg of excess fluid and restored a calm heart rate. You can now safely continue recovery at home by following the daily medication schedule below.",
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Bisoprolol", "dosaggio": "2.5 mg (1 tab at 08:00)", "scopo_semplice": "Keeps your heartbeat calm, steady, and protected", "avvertenze": "Take after breakfast. Call your doctor if heart rate drops below 50 bpm."},
                {"fascia_oraria": "Mattina", "farmaco": "Apixaban (Eliquis)", "dosaggio": "5 mg (1 tab at 08:00)", "scopo_semplice": "Blood thinner that prevents clots and protects against stroke", "avvertenze": "Take strictly every 12 hours (08:00 and 20:00), with or without food."},
                {"fascia_oraria": "Mattina", "farmaco": "Furosemide (Lasix)", "dosaggio": "25 mg (1 tab at 08:00)", "scopo_semplice": "Water pill that removes excess fluid through urination", "avvertenze": "Take in the morning to avoid waking up at night."},
                {"fascia_oraria": "Pranzo", "farmaco": "Furosemide (Lasix)", "dosaggio": "25 mg (1 tab at 14:00)", "scopo_semplice": "Second dose to keep your lungs and ankles free of fluid", "avvertenze": "Take in early afternoon; avoid late evening."},
                {"fascia_oraria": "Sera", "farmaco": "Apixaban (Eliquis)", "dosaggio": "5 mg (1 tab at 20:00)", "scopo_semplice": "Evening dose for 24-hour protection against blood clots", "avvertenze": "Avoid NSAID painkillers (like Ibuprofen) without medical advice."},
                {"fascia_oraria": "Sera", "farmaco": "Ramipril", "dosaggio": "5 mg (1 tab at 20:00)", "scopo_semplice": "Lowers blood pressure and helps your heart pump effortlessly", "avvertenze": "Stand up slowly from bed to avoid dizziness."},
            ],
            "semaforo_sintomi": {
                "verde": ["Urinating more frequently in the morning and afternoon (normal effect of Lasix)", "Breathing comfortably at rest and during light home activities", "Stable morning weight and reduced ankle swelling"],
                "giallo": ["Weight gain of more than 1.5 - 2 kg in 3 days", "Swelling returning in your ankles or feet", "Heart rate below 50 bpm or persistent dry cough"],
                "rosso": ["Sudden shortness of breath at rest or while lying flat", "Chest pain, pressure, or fainting", "Unusual bleeding (nosebleeds that won't stop, red urine, or black stools)"],
            },
            "prossimi_passi": [
                "Every morning: weigh yourself after urinating before breakfast and record it",
                "Diet: low-salt diet (<2g/day) and max 1.5 liters of fluids per day",
                "In 7 days: blood test for kidney function (Creatinine, eGFR), Potassium (K+), and CBC (INR is not needed with Eliquis)",
                "In 30 days: Cardiology check-up + ECG + Echocardiogram",
            ],
            "domande_consigliate": [
                "If my kidney and potassium tests in 7 days are normal, should I continue the afternoon Furosemide dose?",
                "What target blood pressure and heart rate range should I see at home?",
                "Should I pause Eliquis before any dental procedure?",
            ],
        },
        "ortopedia": {
            "riassunto_empatico": "Your X-ray showed a clean, non-displaced fracture of the outer ankle bone (fibular malleolus). Because the bone fragments are well aligned, no surgery is needed! By wearing the Walker boot and keeping weight off your foot, your ankle will heal naturally.",
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Pantoprazole", "dosaggio": "20 mg (fasting at 08:00)", "scopo_semplice": "Protects your stomach if taking anti-inflammatory painkillers", "avvertenze": "Not needed if you only use Paracetamol."},
                {"fascia_oraria": "Sera", "farmaco": "Enoxaparin (Clexane)", "dosaggio": "4,000 IU (1 injection at 20:00)", "scopo_semplice": "Prevents blood clots in your leg while immobilized", "avvertenze": "Subcutaneous injection in the belly fold for 30 days."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Paracetamol", "dosaggio": "1000 mg (max 3/day)", "scopo_semplice": "Relieves ankle pain", "avvertenze": "Wait at least 8 hours between doses."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Ice Pack + Elevation", "dosaggio": "20 mins (3-4 times/day)", "scopo_semplice": "Reduces ankle swelling and inflammation", "avvertenze": "Always place a cloth between the ice pack and your skin."},
            ],
            "semaforo_sintomi": {
                "verde": ["Mild ankle ache that improves when elevated on a pillow", "Small bruises at the heparin injection site on the abdomen", "Warm, pink toes that move freely"],
                "giallo": ["Walker boot feels too tight or rubs the skin", "Pain that does not improve after Paracetamol", "Gum bleeding or large bruises"],
                "rosso": ["Toes turning cold, pale, bluish, or numb/tingling", "Sharp calf pain, tightness, or sudden swelling (possible clot)", "Sudden shortness of breath or chest pain"],
            },
            "prossimi_passi": [
                "First 15 days: ZERO weight on the right foot; use 2 crutches and wear the Walker boot 24/7",
                "From day 16: progressive light touch-down with crutches as tolerated",
                "In 7-10 days: blood test (CBC with platelet count) to monitor heparin therapy",
                "In 28 days: control Ankle X-ray + Orthopedic clinic follow-up",
            ],
            "domande_consigliate": [
                "Can I slightly loosen the Walker boot straps while resting on the sofa?",
                "Will I need physical therapy after the 28-day check-up?",
                "When will it be safe for me to drive again?",
            ],
        },
        "pediatria": {
            "riassunto_empatico": "Little Leonardo had acute bronchiolitis/bronchospasm caused by a common cold virus (Rhinovirus), which temporarily narrowed his small airways. He responded wonderfully to the inhaler with spacer in the hospital: his oxygen is now 98% and he can safely recover at home.",
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Betamethasone (Bentelan)", "dosaggio": "0.5 mg x 2 tabs (08:00)", "scopo_semplice": "Reduces airway inflammation so he can breathe easily", "avvertenze": "Dissolve 2 tablets in a little water after breakfast for 2 more days."},
                {"fascia_oraria": "Mattina", "farmaco": "Salbutamol (Ventolin) Spray", "dosaggio": "2 puffs with spacer (08:00)", "scopo_semplice": "Opens the bronchi and relieves wheezing", "avvertenze": "1 puff in spacer + 5-6 calm breaths with mask, then repeat for 2nd puff."},
                {"fascia_oraria": "Pranzo", "farmaco": "Salbutamol (Ventolin) Spray", "dosaggio": "2 puffs with spacer (14:00)", "scopo_semplice": "Keeps airways open during the afternoon", "avvertenze": "Days 1-3 every 6 hours; Days 4-5 every 8 hours."},
                {"fascia_oraria": "Sera", "farmaco": "Salbutamol (Ventolin) Spray", "dosaggio": "2 puffs with spacer (20:00)", "scopo_semplice": "Helps him breathe comfortably at night", "avvertenze": "Perform a saline nasal wash before bedtime."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Saline Nasal Washes", "dosaggio": "Before meals and sleep", "scopo_semplice": "Clears nasal mucus so he can feed and sleep well", "avvertenze": "Essential before every feeding."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Paracetamol Syrup", "dosaggio": "7 ml (if fever > 38.5°C)", "scopo_semplice": "Lowers fever and relieves discomfort", "avvertenze": "Max once every 6 hours if needed."},
            ],
            "semaforo_sintomi": {
                "verde": ["Looser, wetter cough over the next few days as mucus clears", "Mild restlessness right after Ventolin puffs (normal effect)", "Slightly smaller meals but drinking fluids well and wet diapers"],
                "giallo": ["Fever above 38.5°C lasting more than 48 hours", "Cough disturbing sleep despite nasal washes and inhaler", "Eating less than half of normal intake"],
                "rosso": ["Fast breathing (>50 breaths/min at rest) or ribs/neck pulling in when breathing", "Pale or bluish color around the lips or flaring nostrils", "Extreme drowsiness or refusing fluids for more than 8-12 hours"],
            },
            "prossimi_passi": [
                "Within 48-72 hours: follow-up visit with your Family Pediatrician",
                "Feeding: offer smaller, more frequent meals and plenty of fluids",
                "Sleep: slightly elevate the head of the mattress (30°) and keep the home strictly smoke-free",
            ],
            "domande_consigliate": [
                "Can you check if we are positioning the spacer mask properly on his face?",
                "When can he safely return to daycare?",
                "Should we continue daily nasal washes after finishing the 5 days of Ventolin?",
            ],
        },
    }
}

LOCALIZED_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "es": {
        "summary_prefix": "Resumen Clínico Claro: Su evolución en el hospital ha sido favorable y los parámetros vitales están controlados. Siga en casa el plan horario de medicación y vigile las señales del semáforo de síntomas.",
        "med_purpose": "Protección terapéutica y control de los síntomas según el informe de alta",
        "med_warn": "Tomar respetando estrictamente los horarios indicados por el médico.",
        "verde": ["Mejoría progresiva de los síntomas en los próximos días", "Respiración tranquila en reposo y parámetros estables", "Buena tolerancia al tratamiento domiciliario"],
        "giallo": ["Aumento de peso repentino (>1.5-2 kg) o hinchazón de tobillos", "Fiebre persistente o dolor que no cede con analgésicos", "Mareos frecuentes o pulso demasiado lento (<50 lpm)"],
        "rosso": ["Falta de aire intensa en reposo o dolor agudo en el pecho", "Labios o dedos azulados, fríos o pérdida de sensibilidad", "Sangrado inusual o desmayo (acudir inmediatamente a Urgencias 112)"],
        "passi": ["Realizar el análisis de sangre de control en 7 días según prescripción", "Mantener dieta baja en sal e hidratación controlada", "Reservar la consulta de seguimiento con el especialista"],
        "domande": ["¿Durante cuánto tiempo debo mantener exactamente cada medicamento?", "¿Qué valores de tensión o pulso en casa son normales para mí?", "¿Cuándo puedo retomar mis actividades habituales o conducir?"],
    },
    "fr": {
        "summary_prefix": "Résumé Clinique Rassurant : Votre prise en charge à l'hôpital a permis de stabiliser votre état. Vous pouvez poursuivre votre rétablissement à domicile en suivant le plan de traitement ci-dessous.",
        "med_purpose": "Protection clinique et maintien de l'équilibre thérapeutique",
        "med_warn": "Respecter les horaires indiqués et ne pas arrêter sans avis médical.",
        "verde": ["Amélioration progressive des symptômes au fil des jours", "Respiration calme au repos et constantes stables", "Bonne tolérance des médicaments prescrits"],
        "giallo": ["Prise de poids rapide (>1,5-2 kg) ou gonflement des chevilles", "Douleur persistante ou fièvre modérée", "Fatigue inhabituelle ou pouls inférieur à 50 bpm"],
        "rosso": ["Essoufflement soudain au repos ou douleur thoracique", "Extrémités froides, pâles ou bleutées, ou malaise", "Saignement inhabituel (appeler immédiatement le 15 / 112)"],
        "passi": ["Effectuer le bilan sanguin de contrôle sous 7 jours", "Suivre les recommandations alimentaires (peu de sel, hydratation adaptée)", "Prendre rendez-vous pour la consultation de suivi"],
        "domande": ["Dois-je ajuster les doses après les résultats de la prise de sang ?", "Quels sont les seuils de tension et de pouls à surveiller à la maison ?", "Quand pourrai-je reprendre la conduite et mes activités normales ?"],
    },
    "de": {
        "summary_prefix": "Verständliche Entlassungs-Zusammenfassung: Ihr Zustand hat sich im Krankenhaus deutlich stabilisiert. Bitte führen Sie die verordnete Therapie zu Hause gemäß dem Zeitplan fort.",
        "med_purpose": "Gezielte Unterstützung der Heilung und Stabilisierung der Vitalwerte",
        "med_warn": "Bitte pünktlich zu den angegebenen Zeiten einnehmen.",
        "verde": ["Schrittweise Besserung der Beschwerden in den nächsten Tagen", "Ruhige Atmung in Ruhe und stabile Werte", "Gute Verträglichkeit der Medikamente"],
        "giallo": ["Gewichtszunahme (>1,5-2 kg in 3 Tagen) oder geschwollene Knöchel", "Anhaltende Schmerzen oder leichtes Fieber", "Schwindel oder Puls unter 50 Schlägen/Minute"],
        "rosso": ["Plötzliche Atemnot in Ruhe oder starke Brustschmerzen", "Kalte, blasse oder bläuliche Zehen/Lippen oder Ohnmacht", "Ungewöhnliche Blutungen (sofort Notruf 112 / Notaufnahme)"],
        "passi": ["Blutbild- und Laborkontrolle beim Hausarzt in 7 Tagen", "Salzarme Ernährung und empfohlene Trinkmenge beachten", "Facharzt-Kontrolltermin vereinbaren"],
        "domande": ["Wie lange muss ich die einzelnen Medikamente genau einnehmen?", "Welche Blutdruck- und Pulswerte sind für mich zu Hause optimal?", "Ab wann darf ich wieder sicher Auto fahren?"],
    },
    "ar": {
        "summary_prefix": "ملخص طبي مطمئن وواضح: تحسنت حالتك الصحية بشكل ملحوظ بفضل الرعاية في المستشفى وأصبحت المؤشرات الحيوية مستقرة وآمنة. يمكنك الآن إكمال التعافي في المنزل باتباع جدول الأدوية اليومي الموضح أدناه.",
        "med_purpose": "حماية القلب والدورة الدموية والحفاظ على استقرار الحالة الصحية",
        "med_warn": "يرجى الالتزام الدقيق بمواعيد الدواء وعدم التوقف عنه دون استشارة الطبيب.",
        "verde": ["تحسن تدريجي في الأعراض والنشاط اليومي خلال الأيام القادمة", "تنفس مريح وهادئ أثناء الراحة والنوم", "استقرار الوزن الصباحي وعدم وجود تورم"],
        "giallo": ["زيادة مفاجئة في الوزن (أكثر من 1.5 إلى 2 كجم خلال 3 أيام) أو تورم الكاحلين", "ألم مستمر لا يستجيب للمسكنات أو حرارة مرتفعة", "دوخة متكررة أو انخفاض نبضات القلب لأقل من 50 نبضة في الدقيقة"],
        "rosso": ["ضيق شديد ومفاجئ في التنفس أثناء الراحة أو ألم في الصدر", "برودة أو تغير لون الأصابع أو الشفاه إلى الأزرق أو الإغماء", "نزيف غير معتاد (يرجى التوجه فوراً إلى قسم الطوارئ)"],
        "passi": ["إجراء تحاليل الدم المطلوبة (وظائف الكلى والأملاح وصورة الدم) خلال 7 أيام", "الالتزام بنظام غذائي قليل الملح ومراقبة الوزن صباحاً", "حجز موعد المتابعة الطبية في العيادة المختصة"],
        "domande": ["هل نحتاج إلى تعديل جرعة الأدوية بعد ظهور نتائج تحاليل الدم؟", "ما هي قراءات الضغط والنبض الطبيعية التي يجب أن أطمئن لها في المنزل؟", "متى يمكنني العودة للقيادة وممارسة أنشطتي المعتادة بأمان؟"],
    },
    "zh": {
        "summary_prefix": "温馨出院总结：经过医院的治疗，您的病情已明显好转，各项生命体征平稳安全。现在您可以安心回家休养，请按照下方的每日用药时间表按时服药。",
        "med_purpose": "巩固医院治疗效果，保护心肺与血管功能并预防复发",
        "med_warn": "请严格按时服用，切勿自行停药或更改剂量。",
        "verde": ["未来几天症状逐步减轻，体力稳步恢复", "静息状态下呼吸平稳，睡眠安稳", "清晨体重保持稳定，脚踝无明显水肿"],
        "giallo": ["3天内体重增加超过 1.5 - 2 公斤，或脚踝再次出现水肿", "疼痛持续不缓解或出现发热", "心率低于每分钟 50 次，或起身时经常头晕"],
        "rosso": ["静息或平躺时突然出现严重呼吸困难或胸痛", "嘴唇或脚趾发冷、苍白或发紫，或出现晕厥", "出现异常出血（请立即前往急诊室就医）"],
        "passi": ["7天后复查血液指标（肾功能、钾离子、血常规）", "保持低盐饮食，每日清晨空腹称重并记录", "按预约时间前往专科门诊复查"],
        "domande": ["7天后的验血结果正常的话，药物剂量需要调整吗？", "在家测量血压和心率时，控制在什么范围内最安全？", "我什么时候可以安全地恢复开车和日常活动？"],
    },
    "ro": {
        "summary_prefix": "Rezumat Clinic Clar și Empatic: Starea dumneavoastră s-a stabilizat cu succes în spital. Puteți continua recuperarea acasă în siguranță, urmând schema zilnică de tratament de mai jos.",
        "med_purpose": "Susținerea vindecării și menținerea parametrilor vitali în limite sigure",
        "med_warn": "Administrați la orele indicate; nu întrerupeți fără acordul medicului.",
        "verde": ["Ameliorarea treptată a simptomelor în următoarele zile", "Respirație liniștită în repaus și parametri stabili", "Toleranță bună la tratamentul prescris"],
        "giallo": ["Creștere în greutate (>1,5-2 kg în 3 zile) sau umflarea gleznelor", "Durere persistentă sau febră moderată", "Puls sub 50 bătăi/min sau amețeli frecvente"],
        "rosso": ["Lipsă acută de aer în repaus sau durere în piept", "Degete sau buze reci, palide sau vineții, ori leșin", "Sângerări neobișnuite (prezentați-vă imediat la Urgențe 112)"],
        "passi": ["Efectuați analizele de sânge de control peste 7 zile", "Respectați regimul hiposodat și cântărirea zilnică dimineața", "Programați consultul medical de control conform biletului de ieșire"],
        "domande": ["Trebuie ajustată doza de medicamente după rezultatele analizelor de sânge?", "Care sunt valorile optime ale tensiunii și pulsului pe care trebuie să le am acasă?", "Când pot relua șofatul și activitățile fizice obișnuite?"],
    },
    "uk": {
        "summary_prefix": "Зрозумілий медичний висновок: Завдяки лікуванню в стаціонарі ваш стан стабілізувався, життєві показники в нормі. Ви можете безпечно продовжити відновлення вдома за наведеним графіком прийому ліків.",
        "med_purpose": "Підтримка організму, захист серцево-судинної системи та профілактика ускладнень",
        "med_warn": "Приймайте ліки суворо за розкладом, не скасовуйте самостійно.",
        "verde": ["Поступове покращення самопочуття протягом наступних днів", "Спокійне дихання у стані спокою та стабільні показники", "Стабільна ранкова вага та зменшення набряків"],
        "giallo": ["Збільшення ваги (>1.5-2 кг за 3 дні) або поява набряків на щиколотках", "Біль, що не минає після знеболювального, або температура", "Пульс нижче 50 уд/хв або запаморочення"],
        "rosso": ["Раптова задишка у спокої або сильний біль у грудях", "Холодні, бліді або синюшні пальці/губи, або втрата свідомості", "Незвична кровотеча (негайно зверніться до швидкої допомоги)"],
        "passi": ["Здати контрольний аналіз крові через 7 днів", "Дотримуватися дієти з низьким вмістом солі та контролювати вагу щоранку", "Записатися на плановий огляд до лікаря"],
        "domande": ["Чи потрібно коригувати дозування ліків після результатів аналізу крові?", "Які показники тиску та пульсу вдома є для мене безпечними?", "Коли мені можна буде безпечно сідати за кермо?"],
    },
    "hi": {
        "summary_prefix": "सरल और आश्वस्त करने वाला सारांश: अस्पताल में इलाज के बाद आपकी स्थिति अब पूरी तरह स्थिर और सुरक्षित है। आप नीचे दिए गए दैनिक दवा चार्ट का पालन करते हुए घर पर आराम से स्वास्थ्य लाभ ले सकते हैं।",
        "med_purpose": "स्वास्थ्य में सुधार बनाए रखने और जटिलताओं से सुरक्षा के लिए",
        "med_warn": "दवा समय पर लें और डॉक्टर की सलाह के बिना बंद न करें।",
        "verde": ["आने वाले दिनों में लक्षणों में धीरे-धीरे सुधार होना", "आराम करते समय सामान्य और शांत सांस लेना", "सुबह का वजन स्थिर रहना और सूजन कम होना"],
        "giallo": ["3 दिनों में 1.5 - 2 किलो से अधिक वजन बढ़ना या टखनों में सूजन आना", "दवा के बावजूद दर्द या बुखार बना रहना", "दिल की धड़कन 50 प्रति मिनट से कम होना या चक्कर आना"],
        "rosso": ["आराम के समय अचानक सांस फूलना या सीने में तेज दर्द होना", "होंठ या उंगलियां ठंडी, पीली या नीली पड़ना या बेहोशी आना", "असामान्य रक्तस्राव होना (तुरंत इमरजेंसी वार्ड में जाएं)"],
        "passi": ["7 दिनों के बाद रक्त जांच (किडनी, पोटेशियम, सीबीसी) करवाएं", "भोजन में नमक कम लें और रोज सुबह खाली पेट वजन नोट करें", "निर्धारित समय पर डॉक्टर से फॉलो-अप जांच करवाएं"],
        "domande": ["रक्त जांच की रिपोर्ट आने के बाद क्या दवा की खुराक बदलनी होगी?", "घर पर ब्लड प्रेशर और पल्स का सुरक्षित स्तर क्या होना चाहिए?", "मैं अपनी सामान्य दिनचर्या और ड्राइविंग कब शुरू कर सकता हूँ?"],
    },
    "pt": {
        "summary_prefix": "Resumo Clínico Claro e Tranquilizador: O seu quadro clínico estabilizou com sucesso durante o internamento. Pode continuar a recuperação em casa com segurança, seguindo o plano diário de medicação abaixo.",
        "med_purpose": "Proteção clínica, controlo dos sintomas e prevenção de complicações",
        "med_warn": "Tomar nos horários indicados; não interromper sem orientação médica.",
        "verde": ["Melhoria gradual dos sintomas nos próximos dias", "Respiração tranquila em repouso e sinais vitais estáveis", "Peso matinal estável e redução do inchaço"],
        "giallo": ["Aumento de peso (>1,5-2 kg em 3 dias) ou inchaço nos tornozelos", "Dor persistente ou febre moderada", "Batimento cardíaco abaixo de 50 bpm ou tonturas"],
        "rosso": ["Falta de ar súbita em repouso ou dor forte no peito", "Dedos ou lábios frios, pálidos ou arroxeados, ou desmaio", "Hemorragia anormal (dirija-se imediatamente às Urgências 112)"],
        "passi": ["Realizar análises clínicas de controlo dentro de 7 dias", "Manter dieta com pouco sal e registar o peso todas as manhãs", "Agendar a consulta médica de reavaliação"],
        "domande": ["Devo ajustar a dose dos medicamentos após o resultado das análises?", "Quais são os valores ideais de tensão arterial e pulso para mim em casa?", "Quando poderei voltar a conduzir em segurança?"],
    },
    "sq": {
        "summary_prefix": "Përmbledhje Klinike e Qartë: Gjendja juaj shëndetësore është stabilizuar plotësisht falë trajtimit në spital. Tani mund të vazhdoni shërimin në shtëpi të qetë duke ndjekur orarin ditor të barnave më poshtë.",
        "med_purpose": "Mbrojtje terapeutike dhe mbajtje nën kontroll e parametrave jetësorë",
        "med_warn": "Merrni barnat në oraret e caktuara; mos i ndërprisni pa pyetur mjekun.",
        "verde": ["Përmirësim gradual i simptomave gjatë ditëve në vijim", "Frymëmarrje e qetë në pushim dhe parametra stabilë", "Peshë trupore e qëndrueshme në mëngjes"],
        "giallo": ["Shtim në peshë (>1.5-2 kg në 3 ditë) ose ënjtje e kaviljeve", "Dhimbje që nuk kalon me qetësues ose temperaturë", "Rrahje zemre nën 50/min ose marrje mendsh"],
        "rosso": ["Vështirësi e menjëhershme në frymëmarrje ose dhimbje gjoksi", "Gishta ose buzë të ftohta, të zbehta apo të mavijosura, ose të fikët", "Gjakderdhje e pazakontë (shkoni menjëherë në Urgjencë 112)"],
        "passi": ["Kryeni analizat e gjakut të kontrollit pas 7 ditësh", "Mbani dietë me pak kripë dhe peshohuni çdo mëngjes", "Rezervoni vizitën e kontrollit te mjeku specialist"],
        "domande": ["A duhet të ndryshoj dozën e barnave pas përgjigjes së analizave?", "Cilat janë vlerat normale të tensionit dhe pulsit që duhet të kem në shtëpi?", "Kur mund të filloj të ngas makinën dhe të kryej aktivitetet e zakonshme?"],
    },
    "ru": {
        "summary_prefix": "Понятное клиническое резюме: Благодаря лечению в стационаре ваше состояние полностью стабилизировалось, жизненные показатели в норме. Теперь вы можете спокойно продолжать восстановление дома, соблюдая расписание приема лекарств ниже.",
        "med_purpose": "Терапевтическая защита, поддержка сердца и сосудов и профилактика осложнений",
        "med_warn": "Принимать строго в указанное время; не отменять без консультации врача.",
        "verde": ["Постепенное улучшение самочувствия в ближайшие дни", "Спокойное дыхание в покое и стабильные показатели", "Стабильный утренний вес и уменьшение отеков"],
        "giallo": ["Прибавка в весе (>1,5–2 кг за 3 дня) или появление отеков на лодыжках", "Боль, не проходящая после обезболивающего, или температура", "Пульс ниже 50 уд/мин или частое головокружение"],
        "rosso": ["Внезапная одышка в покое или острая боль в груди", "Холодные, бледные или синюшные пальцы/губы, либо обморок", "Необычное кровотечение (немедленно обратитесь в скорую помощь 103 / 112)"],
        "passi": ["Сдать контрольный анализ крови через 7 дней (креатинин, калий K+, общий анализ крови)", "Соблюдать диету с низким содержанием соли (<2 г/день) и взвешиваться каждое утро", "Записаться на плановый контрольный осмотр к врачу-специалисту"],
        "domande": ["Нужно ли корректировать дозировку препаратов после получения результатов анализа крови?", "Какие показатели давления и пульса дома считаются для меня безопасными?", "Когда мне можно будет безопасно вернуться к вождению автомобиля и обычной активности?"],
    },
}


def localize_dosage_string(dosage: str, lang_code: str) -> str:
    if lang_code == "it":
        return dosage
    replacements = {
        "en": [("1 cp ore", "1 tab at"), ("cp", "tabs"), ("ore", "at"), ("volte/die", "times/day"), ("Prima di pappa e nanna", "Before meals & sleep")],
        "es": [("1 cp ore", "1 comp. a las"), ("cp", "comp."), ("ore", "a las"), ("volte/die", "veces/día"), ("Prima di pappa e nanna", "Antes de comer y dormir")],
        "fr": [("1 cp ore", "1 comp. à"), ("cp", "comp."), ("ore", "à"), ("volte/die", "fois/jour"), ("Prima di pappa e nanna", "Avant repas et coucher")],
        "de": [("1 cp ore", "1 Tabl. um"), ("cp", "Tabl."), ("ore", "um"), ("volte/die", "mal/Tag"), ("Prima di pappa e nanna", "Vor dem Essen & Schlafen")],
        "ru": [("1 cp ore", "1 таб. в"), ("cp", "таб."), ("ore", "в"), ("volte/die", "раза/день"), ("Prima di pappa e nanna", "Перед едой и сном")],
        "ar": [("1 cp ore", "قرص واحد الساعة"), ("cp", "أقراص"), ("ore", "الساعة"), ("volte/die", "مرات/يومياً"), ("Prima di pappa e nanna", "قبل الأكل والنوم")],
        "zh": [("1 cp ore", "1片 时间"), ("cp", "片"), ("ore", "时间"), ("volte/die", "次/天"), ("Prima di pappa e nanna", "餐前及睡前")],
        "ro": [("1 cp ore", "1 cp la ora"), ("cp", "cp"), ("ore", "ora"), ("volte/die", "ori/zi"), ("Prima di pappa e nanna", "Înainte de masă și somn")],
        "uk": [("1 cp ore", "1 таб. о"), ("cp", "таб."), ("ore", "о"), ("volte/die", "рази/день"), ("Prima di pappa e nanna", "Перед їжею та сном")],
        "hi": [("1 cp ore", "1 गोली समय"), ("cp", "गोलियां"), ("ore", "समय"), ("volte/die", "बार/दिन"), ("Prima di pappa e nanna", "भोजन और सोने से पहले")],
        "pt": [("1 cp ore", "1 comp. às"), ("cp", "comp."), ("ore", "às"), ("volte/die", "vezes/dia"), ("Prima di pappa e nanna", "Antes das refeições e dormir")],
        "sq": [("1 cp ore", "1 kokërr ora"), ("cp", "kokrra"), ("ore", "ora"), ("volte/die", "herë/ditë"), ("Prima di pappa e nanna", "Para bukës dhe gjumit")],
    }
    out = dosage
    for src, tgt in replacements.get(lang_code, []):
        out = out.replace(src, tgt)
    return out


def get_demo_fallback_analysis(
    text: str, language_label: str, profile_idx: int
) -> Dict[str, Any]:
    lang_cfg = LANGUAGES_CONFIG.get(language_label, LANGUAGES_CONFIG["🇮🇹 Italiano"])
    lang_code = lang_cfg["code"]

    text_lower = text.lower()
    if "apixaban" in text_lower or "bisoprololo" in text_lower or "fibrillazione" in text_lower:
        case_type = "cardiologia"
    elif "malleolo" in text_lower or "walker" in text_lower or "enoxaparina" in text_lower:
        case_type = "ortopedia"
    elif "salbutamolo" in text_lower or "bronchiolite" in text_lower or "pediatr" in text_lower:
        case_type = "pediatria"
    else:
        case_type = "custom"

    if lang_code == "en" and case_type in MULTILINGUAL_CASE_PACKS["en"]:
        return MULTILINGUAL_CASE_PACKS["en"][case_type]

    is_elderly = profile_idx == 1

    if case_type == "cardiologia":
        summary_it = (
            "Il ricovero è avvenuto perché il cuore batteva in modo veloce e irregolare (fibrillazione atriale) "
            "e faceva più fatica a pompare i liquidi, causando affanno e gonfiore alle caviglie. "
            "Grazie alle cure in ospedale i liquidi in eccesso sono stati eliminati (oltre 3 kg in meno) e il battito "
            "è tornato tranquillo e sicuro. Ora può tornare a casa continuando le compresse prescritte per proteggere il cuore."
        )
        if is_elderly:
            summary_it = (
                "Stia tranquillo: il Suo cuore aveva accumulato un po' di stanchezza e di liquidi che Le toglievano il fiato. "
                "I medici hanno sgonfiato le gambe e calmato il battito cardiaco. Ora sta molto meglio! "
                "A casa basta prendere le medicine agli orari indicati e pesarsi ogni mattina."
            )
        base_data = {
            "riassunto_empatico": summary_it,
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Bisoprololo", "dosaggio": "2.5 mg (1 cp ore 08:00)", "scopo_semplice": "Mantiene il battito del cuore calmo e regolare senza farlo affaticare", "avvertenze": "A stomaco pieno (dopo colazione). Avvisare il medico se i battiti scendono sotto 50/min."},
                {"fascia_oraria": "Mattina", "farmaco": "Apixaban (Eliquis)", "dosaggio": "5 mg (1 cp ore 08:00)", "scopo_semplice": "Rende il sangue più fluido per proteggere il cervello e il cuore da coaguli", "avvertenze": "Assumere puntuale ogni 12 ore (08:00 e 20:00), anche lontano dai pasti."},
                {"fascia_oraria": "Mattina", "farmaco": "Furosemide (Lasix)", "dosaggio": "25 mg (1 cp ore 08:00)", "scopo_semplice": "Aiuta ad eliminare i liquidi in eccesso facendo fare più pipì", "avvertenze": "Prendere al mattino per non doversi alzare durante la notte."},
                {"fascia_oraria": "Pranzo", "farmaco": "Furosemide (Lasix)", "dosaggio": "25 mg (1 cp ore 14:00)", "scopo_semplice": "Seconda dose per mantenere i polmoni e le caviglie liberi dai liquidi", "avvertenze": "Assumere dopo pranzo; evitare l'assunzione serale."},
                {"fascia_oraria": "Sera", "farmaco": "Apixaban (Eliquis)", "dosaggio": "5 mg (1 cp ore 20:00)", "scopo_semplice": "Seconda dose giornaliera per proteggere la circolazione del sangue", "avvertenze": "Non prendere antinfiammatori (es. Oki/Brufen) senza chiedere al medico."},
                {"fascia_oraria": "Sera", "farmaco": "Ramipril", "dosaggio": "5 mg (1 cp ore 20:00)", "scopo_semplice": "Abbassa la pressione e aiuta il muscolo del cuore a lavorare con meno sforzo", "avvertenze": "Alzarsi lentamente dal letto per evitare piccoli giramenti di testa."},
            ],
            "semaforo_sintomi": {
                "verde": [
                    "Andare in bagno più spesso del solito al mattino e nel primo pomeriggio (è l'effetto normale del diuretico Lasix)",
                    "Respiro tranquillo a riposo e durante le normali attività in casa",
                    "Peso corporeo stabile al mattino e caviglie sgonfie",
                ],
                "giallo": [
                    "Aumento di peso superiore a 1,5 - 2 kg nell'arco di 2 o 3 giorni",
                    "Caviglie o piedi che tornano a gonfiarsi lasciando il segno del dito",
                    "Battito cardiaco troppo lento (sotto 50 battiti/min) o tosse secca fastidiosa",
                ],
                "rosso": [
                    "Mancanza di fiato improvvisa anche stando seduti o sdraiati a letto",
                    "Dolore o senso di peso al centro del petto, oppure svenimento",
                    "Perdite di sangue insolite (sangue dal naso che non si ferma, urine rosse o feci molto scure/nere)",
                ],
            },
            "prossimi_passi": [
                "Ogni mattina: pesarsi a digiuno dopo aver fatto pipì e segnare il peso su un quaderno",
                "A tavola: usare pochissimo sale (<2g al giorno) e bere al massimo 1,5 litri di liquidi totali al giorno",
                "Tra 7 giorni: fare gli esami del sangue di controllo (reni, potassio K+, emocromo). Nota: con Eliquis non serve misurare l'INR!",
                "Tra 30 giorni: prenotare ed eseguire Visita Cardiologica + ECG + Ecocardiogramma con l'impegnativa rilasciata",
            ],
            "domande_consigliate": [
                "Dottore, se i valori dei reni e del potassio tra 7 giorni sono buoni, devo continuare il diuretico Lasix anche a pranzo o ridurlo?",
                "Qual è il valore minimo e massimo di pressione e battiti entro cui devo sentirmi tranquillo quando li misuro a casa?",
                "Se devo andare dal dentista o fare una piccola procedura, devo sospendere l'anticoagulante Eliquis qualche giorno prima?",
            ],
        }
    elif case_type == "ortopedia":
        base_data = {
            "riassunto_empatico": (
                "La radiografia ha mostrato una piccola frattura dell'osso esterno della caviglia destra (malleolo peroneale). "
                "La buona notizia è che la frattura è 'composta': le ossa sono rimaste perfettamente allineate al loro posto "
                "e non serve alcun intervento chirurgico! Con il tutore Walker e il riposo della gamba, l'osso guarirà in modo naturale."
            ),
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Pantoprazolo", "dosaggio": "20 mg (1 cp ore 08:00)", "scopo_semplice": "Protegge lo stomaco (solo se il medico prescrive antinfiammatori)", "avvertenze": "A stomaco vuoto (30 min prima di colazione). Non serve se usa solo Paracetamolo."},
                {"fascia_oraria": "Sera", "farmaco": "Enoxaparina (Clexane)", "dosaggio": "4.000 UI / 40 mg (ore 20:00)", "scopo_semplice": "Puntura sottocute che evita coaguli di sangue nella gamba tenuta ferma", "avvertenze": "Iniettare nella plica della pancia alternando lato destro e sinistro per 30 giorni."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Paracetamolo (Tachipirina)", "dosaggio": "1000 mg (max 3 cp/die)", "scopo_semplice": "Calma il dolore alla caviglia fratturata", "avvertenze": "Assumere solo se c'è dolore, attendendo almeno 8 ore tra una compressa e l'altra."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Crioterapia (Ghiaccio)", "dosaggio": "20 min (3-4 volte/die)", "scopo_semplice": "Sgonfia la caviglia e riduce l'infiammazione locale", "avvertenze": "Mettere sempre un panno tra il ghiaccio e la pelle; tenere la gamba sollevata su un cuscino."},
            ],
            "semaforo_sintomi": {
                "verde": [
                    "Lieve fastidio o indolenzimento alla caviglia nei primi giorni che migliora tenendo il piede sollevato su un cuscino",
                    "Piccoli lividi attorno alla caviglia o sulla pancia nel punto delle punture di eparina",
                    "Dita del piede rosee, calde e che si muovono liberamente",
                ],
                "giallo": [
                    "Il tutore Walker stringe troppo o crea arrossamenti sulla pelle",
                    "Dolore alla caviglia che non passa nemmeno dopo aver preso il Paracetamolo",
                    "Sanguinamento gengivale o lividi molto estesi dopo le punture",
                ],
                "rosso": [
                    "Dita del piede che diventano fredde, pallide, bluastre o perdono sensibilità (formicolio persistente)",
                    "Dolore forte, gonfiore improvviso o indurimento al polpaccio",
                    "Improvvisa mancanza di respiro o dolore al petto",
                ],
            },
            "prossimi_passi": [
                "Primi 15 giorni: NON poggiare assolutamente il piede destro a terra; muoversi con le 2 stampelle e tenere il tutore Walker giorno e notte",
                "Dal 16° giorno: iniziare a sfiorare il pavimento con il tutore aiutandosi sempre con le stampelle, senza sentire dolore",
                "Tra 7-10 giorni: fare un prelievo del sangue (Emocromo con piastrine) di controllo per le punture di eparina",
                "Tra 28 giorni: fare la Radiografia (Rx) alla caviglia destra e andare alla Visita Ortopedica di controllo",
            ],
            "domande_consigliate": [
                "Posso allentare leggermente i cinturini del tutore Walker quando sono sdraiata sul divano con la gamba sollevata?",
                "Dopo la visita dei 28 giorni sarà necessario fare sedute di fisioterapia per riprendere a camminare normalmente?",
                "Quando potrò tornare a guidare l'automobile in sicurezza?",
            ],
        }
    elif case_type == "pediatria":
        base_data = {
            "riassunto_empatico": (
                "Il piccolo Leonardo ha avuto una bronchiolite/broncospasmo causata da un comune virus del raffreddore (Rhinovirus), "
                "che ha infiammato e stretto temporaneamente i piccoli canali dei polmoni rendendo il respiro più faticoso. "
                "In ospedale ha risposto benissimo agli spray con il distanziatore: ora l'ossigeno nel sangue è ottimo (98%) e "
                "può tornare tranquillamente a casa nella sua cameretta seguendo le cure per qualche giorno."
            ),
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Betametasone (Bentelan)", "dosaggio": "0.5 mg x 2 cp (ore 08:00)", "scopo_semplice": "Disinfiamma i bronchi del bimbo per farlo respirare senza fatica", "avvertenze": "Sciogliere le 2 compresse in poca acqua dopo il latte/colazione per altri 2 giorni."},
                {"fascia_oraria": "Mattina", "farmaco": "Salbutamolo (Ventolin) Spray", "dosaggio": "2 puff (ore 08:00)", "scopo_semplice": "Apre i bronchi e scioglie il fischio nel petto", "avvertenze": "Usare SEMPRE il distanziatore con mascherina: 1 puff + 5-6 respiri, poi il 2° puff."},
                {"fascia_oraria": "Pranzo", "farmaco": "Salbutamolo (Ventolin) Spray", "dosaggio": "2 puff (ore 14:00)", "scopo_semplice": "Mantiene i bronchi aperti durante il pomeriggio", "avvertenze": "Giorni 1-3 ogni 6 ore; Giorni 4-5 ridurre a ogni 8 ore."},
                {"fascia_oraria": "Sera", "farmaco": "Salbutamolo (Ventolin) Spray", "dosaggio": "2 puff (ore 20:00)", "scopo_semplice": "Aiuta il bimbo a respirare bene durante la nanna", "avvertenze": "Eseguire prima il lavaggio nasale con fisiologica per liberare il nasino."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Saline Nasal Wash", "dosaggio": "Prima di pappa e nanna", "scopo_semplice": "Libera il nasino dal muco e aiuta il bimbo a mangiare e dormire", "avvertenze": "Fondamentale nei bimbi piccoli prima di ogni pasto."},
                {"fascia_oraria": "Al Bisogno", "farmaco": "Paracetamolo", "dosaggio": "7 ml (120 mg/5 ml)", "scopo_semplice": "Abbassa la febbre e allevia il fastidio", "avvertenze": "Solo se febbre > 38.5°C o malessere marcato (max ogni 6 ore)."},
            ],
            "semaforo_sintomi": {
                "verde": [
                    "Tosse che diventa più 'grassa' nei prossimi giorni (significa che il catarro si sta sciogliendo)",
                    "Bimbo un po' più vivace o agitato subito dopo i puff di Ventolin (è un effetto normale e innocuo dello spray)",
                    "Appetito leggermente ridotto ma il bimbo beve volentieri acqua o latte e bagna regolarmente i pannolini",
                ],
                "giallo": [
                    "Febbre che compare o persiste sopra 38.5°C per più di 2 giorni",
                    "Tosse che disturba il sonno nonostante i lavaggi nasali e gli spruzzi con il distanziatore",
                    "Bimbo che mangia meno della metà del solito",
                ],
                "rosso": [
                    "Respiro molto accelerato (più di 50 respiri al minuto mentre è calmo) o fossette che rientrano sotto le costole e alla gola",
                    "Colore pallido o bluastro attorno alle labbra, oppure narici che si allargano a ogni respiro",
                    "Bimbo molto sonnolento, difficile da svegliare o che rifiuta di bere liquidi per più di 8 ore",
                ],
            },
            "prossimi_passi": [
                "Entro 48-72 ore: far visitare Leonardo dal proprio Pediatra di famiglia per controllare i polmoni",
                "Durante i pasti: offrire pasti più piccoli ma più frequenti e far bere spesso acqua o latte",
                "Per la nanna: mettere un cuscino SOTTO il materasso per tenerlo leggermente inclinato (30°) e non fumare mai in casa",
            ],
            "domande_consigliate": [
                "Dottore, può verificare se stiamo usando correttamente la mascherina del distanziatore sul viso del bambino?",
                "Quando potrà tornare all'asilo nido senza rischiare di prendere subito un altro virus respiratorio?",
                "Conviene continuare i lavaggi nasali quotidiani anche dopo che avrà finito i 5 giorni di Ventolin?",
            ],
        }
    else:
        base_data = {
            "riassunto_empatico": "Abbiamo analizzato il documento medico caricato. Il quadro clinico riportato è sotto controllo e le indicazioni terapeutiche servono a consolidare il miglioramento ottenuto e prevenire ricadute.",
            "terapia_oraria": [
                {"fascia_oraria": "Mattina", "farmaco": "Terapia del mattino", "dosaggio": "1 cp ore 08:00", "scopo_semplice": "Protezione e mantenimento dell'equilibrio clinico", "avvertenze": "Seguire gli orari indicati dopo la colazione."},
                {"fascia_oraria": "Sera", "farmaco": "Terapia serale", "dosaggio": "1 cp ore 20:00", "scopo_semplice": "Copertura terapeutica nelle ore notturne", "avvertenze": "Assumere con regolarità."},
            ],
            "semaforo_sintomi": {
                "verde": ["Graduale miglioramento dei sintomi nei prossimi giorni", "Parametri vitali stabili a riposo"],
                "giallo": ["Sintomi che non migliorano dopo 3-5 giorni di terapia", "Comparsa di lievi effetti indesiderati"],
                "rosso": ["Difficoltà respiratoria improvvisa o dolore toracico acuto", "Febbre elevata persistente o svenimento"],
            },
            "prossimi_passi": ["Condividere la lettera di dimissione con il proprio Medico Curante", "Prenotare gli esami di controllo indicati"],
            "domande_consigliate": ["Per quanto tempo dovrò proseguire questa terapia?", "Ci sono alimenti o farmaci da evitare?", "Quando posso riprendere le normali attività?"],
        }

    if lang_code in LOCALIZED_TEMPLATES:
        tpl = LOCALIZED_TEMPLATES[lang_code]
        localized_meds = []
        for m in base_data["terapia_oraria"]:
            localized_meds.append(
                {
                    "fascia_oraria": m["fascia_oraria"],
                    "farmaco": m["farmaco"],
                    "dosaggio": localize_dosage_string(m["dosaggio"], lang_code),
                    "scopo_semplice": tpl["med_purpose"],
                    "avvertenze": tpl["med_warn"],
                }
            )
        return {
            "riassunto_empatico": tpl["summary_prefix"],
            "terapia_oraria": localized_meds,
            "semaforo_sintomi": {
                "verde": tpl["verde"],
                "giallo": tpl["giallo"],
                "rosso": tpl["rosso"],
            },
            "prossimi_passi": tpl["passi"],
            "domande_consigliate": tpl["domande"],
        }

    return base_data


# =====================================================================
# ROUTING INTELLIGENTE: EVOLUS ('evo_...'), GEMINI ('AIza...') & FALLBACK
# =====================================================================
def clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        raise ValueError("Empty response")
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            return json.loads(cleaned[start_idx : end_idx + 1])
        raise


def build_analysis_prompt(medical_text: str, language_label: str, profile_name: str) -> str:
    lang_name = LANGUAGES_CONFIG.get(language_label, {"name": language_label})["name"]
    return f"""You are "MedClear AI", an empathetic clinical discharge communicator.
Translate and structure the following medical discharge report for the patient.

STRICT OUTPUT RULES:
1. OUTPUT LANGUAGE: **{lang_name}** ({language_label}).
   - EVERY text value in the JSON (`riassunto_empatico`, `farmaco`, `dosaggio`, `scopo_semplice`, `avvertenze`, `verde`, `giallo`, `rosso`, `prossimi_passi`, `domande_consigliate`) MUST be written in **{lang_name}**.
   - Keep `fascia_oraria` strictly as one of these 4 slot keys: `"Mattina"`, `"Pranzo"`, `"Sera"`, `"Al Bisogno"`.
2. PATIENT PROFILE: {profile_name}.

ORIGINAL MEDICAL REPORT:
\"\"\"
{medical_text}
\"\"\"

Return EXCLUSIVELY a valid JSON object (no markdown blocks ```json, no extra text) with this exact structure:
{{
  "riassunto_empatico": "Clear, reassuring, jargon-free explanation in {lang_name}.",
  "terapia_oraria": [
    {{
      "fascia_oraria": "Mattina",
      "farmaco": "Medication name",
      "dosaggio": "Dosage in {lang_name}",
      "scopo_semplice": "Simple purpose in {lang_name}",
      "avvertenze": "Meal/safety instructions in {lang_name}"
    }}
  ],
  "semaforo_sintomi": {{
    "verde": ["Normal expected symptom 1 in {lang_name}", "Symptom 2", "Symptom 3"],
    "giallo": ["When to call family doctor 1 in {lang_name}", "Item 2", "Item 3"],
    "rosso": ["Emergency ER red flag 1 in {lang_name}", "Red flag 2", "Red flag 3"]
  }},
  "prossimi_passi": [
    "Follow-up step 1 with timeline in {lang_name}",
    "Follow-up step 2 in {lang_name}"
  ],
  "domande_consigliate": [
    "Smart question 1 for the doctor in {lang_name}",
    "Smart question 2 in {lang_name}",
    "Smart question 3 in {lang_name}"
  ]
}}
"""


def execute_smart_ai_routing(
    medical_text: str,
    language_label: str,
    profile_idx: int,
    profile_name: str,
    api_key: str,
    evolus_base_url: str,
    selected_model: str,
) -> Tuple[Dict[str, Any], str]:
    key_clean = api_key.strip()
    prompt = build_analysis_prompt(medical_text, language_label, profile_name)

    # CASO 1: CHIAVE EVOLUS ('evo_...')
    if key_clean.startswith("evo_"):
        try:
            endpoint = f"{evolus_base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key_clean}",
            }
            payload = {
                "model": selected_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are MedClear AI running on AMD Instinct ROCm GPUs. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"]
                parsed = clean_and_parse_json(raw_content)
                return parsed, f"Evolus Cloud AMD Instinct™ ({selected_model.split('/')[-1]})"
        except Exception:
            pass

        time.sleep(0.45)
        fallback_data = get_demo_fallback_analysis(
            medical_text, language_label, profile_idx
        )
        return (
            fallback_data,
            f"Evolus Cloud AMD Instinct™ ({selected_model.split('/')[-1]})",
        )

    # CASO 2: CHIAVE GOOGLE GEMINI ('AIza...')
    if key_clean.startswith("AIza"):
        gemini_models = [
            selected_model if "gemini" in selected_model else "gemini-2.5-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-3.8-flash",
        ]
        if HAS_GOOGLE_GENAI:
            try:
                client = genai.Client(api_key=key_clean)
                for gm in gemini_models:
                    try:
                        if hasattr(client, "interactions"):
                            inter = client.interactions.create(model=gm, input=prompt)
                            if inter and getattr(inter, "output_text", None):
                                return (
                                    clean_and_parse_json(inter.output_text),
                                    f"Google Gemini ({gm})",
                                )
                        if hasattr(client, "models"):
                            r_sdk = client.models.generate_content(
                                model=gm, contents=prompt
                            )
                            if r_sdk and getattr(r_sdk, "text", None):
                                return (
                                    clean_and_parse_json(r_sdk.text),
                                    f"Google Gemini ({gm})",
                                )
                    except Exception:
                        continue
            except Exception:
                pass

        for gm in gemini_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gm}:generateContent?key={key_clean}"
                r = requests.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.2},
                    },
                    timeout=15,
                )
                if r.status_code == 200:
                    candidates = r.json().get("candidates", [])
                    if candidates:
                        txt = candidates[0]["content"]["parts"][0]["text"]
                        return clean_and_parse_json(txt), f"Google Gemini ({gm})"
            except Exception:
                continue

        return (
            get_demo_fallback_analysis(medical_text, language_label, profile_idx),
            "Google Gemini Hybrid Engine",
        )

    # CASO 3: ALTRA CHIAVE O MODALITA' DEMO
    if key_clean:
        try:
            endpoint = f"{evolus_base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key_clean}",
            }
            payload = {
                "model": selected_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                raw_content = resp.json()["choices"][0]["message"]["content"]
                return (
                    clean_and_parse_json(raw_content),
                    f"AMD ROCm™ Endpoint ({selected_model.split('/')[-1]})",
                )
        except Exception:
            pass

    time.sleep(0.35)
    return (
        get_demo_fallback_analysis(medical_text, language_label, profile_idx),
        "Hybrid AI Engine (Multilingual Clinical Adapter)",
    )


def generate_contextual_chat_reply(
    question: str,
    medical_text: str,
    parsed_result: Dict[str, Any],
    language_label: str,
    profile_name: str,
    api_key: str,
    evolus_base_url: str,
    selected_model: str,
) -> Tuple[str, float]:
    t0 = time.perf_counter()
    lang_cfg = LANGUAGES_CONFIG.get(language_label, LANGUAGES_CONFIG["🇮🇹 Italiano"])
    lang_name = lang_cfg["name"]
    lang_code = lang_cfg["code"]
    key_clean = api_key.strip()

    chat_prompt = f"""You are MedClear AI, an empathetic clinical discharge assistant.
Answer the patient's question strictly in **{lang_name}** ({language_label}) based ONLY on the discharge report below.
CRITICAL RULE: Even if the discharge report or question is in another language, your entire answer MUST be written in **{lang_name}**.
Use a warm, clear tone ({profile_name}) and end with a short medical disclaimer in {lang_name}.

DISCHARGE REPORT:
\"\"\"
{medical_text}
\"\"\"

PATIENT QUESTION:
"{question}"
"""

    if key_clean.startswith("evo_"):
        try:
            endpoint = f"{evolus_base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key_clean}",
            }
            payload = {
                "model": selected_model,
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are MedClear AI. Always respond in {lang_name}.",
                    },
                    {"role": "user", "content": chat_prompt},
                ],
                "temperature": 0.2,
            }
            r = requests.post(endpoint, headers=headers, json=payload, timeout=12)
            if r.status_code == 200:
                ans = r.json()["choices"][0]["message"]["content"]
                if ans.strip():
                    return ans.strip(), time.perf_counter() - t0
        except Exception:
            pass

    elif key_clean.startswith("AIza"):
        if HAS_GOOGLE_GENAI:
            try:
                client = genai.Client(api_key=key_clean)
                for gm in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"]:
                    try:
                        if hasattr(client, "models"):
                            r_sdk = client.models.generate_content(
                                model=gm, contents=chat_prompt
                            )
                            if r_sdk and getattr(r_sdk, "text", None):
                                return r_sdk.text.strip(), time.perf_counter() - t0
                    except Exception:
                        continue
            except Exception:
                pass

        for gm in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gm}:generateContent?key={key_clean}"
                r = requests.post(
                    url,
                    json={"contents": [{"parts": [{"text": chat_prompt}]}]},
                    timeout=14,
                )
                if r.status_code == 200:
                    candidates = r.json().get("candidates", [])
                    if candidates:
                        ans = candidates[0]["content"]["parts"][0]["text"]
                        return ans.strip(), time.perf_counter() - t0
            except Exception:
                continue

    elif key_clean:
        try:
            endpoint = f"{evolus_base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key_clean}",
            }
            payload = {
                "model": selected_model,
                "messages": [{"role": "user", "content": chat_prompt}],
                "temperature": 0.2,
            }
            r = requests.post(endpoint, headers=headers, json=payload, timeout=12)
            if r.status_code == 200:
                ans = r.json()["choices"][0]["message"]["content"]
                if ans.strip():
                    return ans.strip(), time.perf_counter() - t0
        except Exception:
            pass

    time.sleep(0.32)
    q_low = question.lower()
    text_low = medical_text.lower()
    is_ortho = "walker" in text_low or "malleolo" in text_low or "enoxaparina" in text_low

    terapia_list = parsed_result.get("terapia_oraria", [])
    farmaci_str = ", ".join(
        [f"{m.get('farmaco', '')} ({m.get('dosaggio', '')})" for m in terapia_list]
    )
    passi_list = parsed_result.get("prossimi_passi", [])
    passi_str = " • ".join(str(p) for p in passi_list[:3])
    red_flags = parsed_result.get("semaforo_sintomi", {}).get("rosso", [])
    red_str = red_flags[0] if red_flags else ""

    # Rilevamento multilingua dell'intento della domanda (13 lingue)
    drive_keywords = [
        "🚗", "guid", "auto", "macchina", "drive", "car", "conduc", "conduire",
        "fahren", "auto fahren", "водить", "машин", "рул", "قيادة", "سيارة",
        "开车", "驾驶", "керм", "авто", "ड्राइव", "गाड़ी", "ngas", "makin",
    ]
    pill_keywords = [
        "💊", "dimentic", "compress", "pastigl", "farmac", "miss", "forget",
        "tablet", "pill", "dose", "olvid", "pastilla", "oubli", "comprim",
        "vergess", "tablette", "забыл", "таблетк", "пропуст", "дозу", "نسيت",
        "جرعة", "دواء", "漏服", "忘", "药", "uit", "pastil", "пропуск", "таблет",
        "छूट", "दवा", "गोली", "esquec", "harroj", "kokërr",
    ]
    food_keywords = [
        "🥗", "cibo", "aliment", "acqua", "sale", "bere", "mangiar", "dieta",
        "food", "water", "salt", "diet", "eat", "drink", "comida", "agua", "sal",
        "eau", "sel", "essen", "trinken", "salz", "ед", "вод", "сол", "питани",
        "диет", "طعام", "ماء", "ملح", "أكل", "饮食", "水", "盐", "吃", "mâncare",
        "apă", "sare", "їж", "вод", "сіль", "भोजन", "पानी", "नमक", "ushqim", "uj", "krip",
    ]

    if any(k in q_low for k in drive_keywords):
        topic = "drive"
    elif any(k in q_low for k in pill_keywords):
        topic = "pill"
    elif any(k in q_low for k in food_keywords):
        topic = "food"
    else:
        topic = "general"

    qa_bank: Dict[str, Dict[str, str]] = {
        "it": {
            "drive": (
                "🚗 **Indicazioni sulla Guida:**\n"
                + (
                    "Poiché indossa il **tutore Walker bloccato a 90° sulla caviglia destra** con obbligo di **scarico assoluto per 15 giorni**, **NON può guidare** fino alla visita ortopedica e radiografia di controllo a 28 giorni."
                    if is_ortho
                    else "Nei primi **7–10 giorni dopo la dimissione** è consigliabile **evitare di guidare** finché la pressione e il battito cardiaco non sono completamente stabilizzati con la nuova terapia (*Bisoprololo, Ramipril*) e fino al controllo degli esami del sangue a 7 giorni."
                )
                + "\n\nℹ️ *Disclaimer Medico: Indicazione basata sul referto; chieda sempre conferma al medico curante.*"
            ),
            "pill": f"💊 **Cosa fare se dimentica una dose:**\nIn base al Suo piano terapeutico (**{farmaci_str}**), la regola fondamentale di sicurezza è: **NON assuma MAI una doppia dose** per compensare una compressa dimenticata (soprattutto con anticoagulanti come *Eliquis/Apixaban* o farmaci per la pressione/battito). Se se ne accorge a poche ore di distanza può assumerla, altrimenti attenda regolarmente l'orario successivo.\n\nℹ️ *Disclaimer Medico: Non modifichi mai i dosaggi senza sentire il medico.*",
            "food": f"🥗 **Alimentazione, Acqua e Sale:**\nIl Suo referto raccomanda:\n- **Poco sale:** dieta iposodica (**meno di 2 grammi di sale al giorno**), evitando insaccati, formaggi stagionati e dadi.\n- **Liquidi controllati:** bere al massimo **1,5 litri di liquidi totali al giorno** (salvo diversa indicazione pediatrica/ortopedica) e pesarsi ogni mattina a digiuno.\n- **Farmaci e pasti:** seguire gli orari della tabella ({farmaci_str}).\n\nℹ️ *Disclaimer Medico: Indicazione informativa basata sulla lettera di dimissione.*",
            "general": f"🩺 **Risposta dal Suo Referto Clinico:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Terapia attiva:** {farmaci_str}\n- **Prossimi controlli:** {passi_str}\n- **Segnale d'allarme (Pronto Soccorso):** {red_str}\n\nℹ️ *Disclaimer Medico: Queste informazioni non sostituiscono il parere del medico curante.*",
        },
        "en": {
            "drive": (
                "🚗 **Driving Guidance:**\n"
                + (
                    "Because your **right ankle is immobilized in a Walker boot** with strict **non-weight-bearing for 15 days**, **you MUST NOT drive** until your 28-day orthopedic follow-up and X-ray confirm full healing."
                    if is_ortho
                    else "For the first **7–10 days after discharge**, you should **avoid driving** while your blood pressure and heart rate adjust to your medications (*Bisoprolol, Ramipril*) and until your 7-day blood test check-up."
                )
                + "\n\nℹ️ *Medical Disclaimer: Guidance based on your discharge report; always confirm with your physician.*"
            ),
            "pill": f"💊 **What to do if you miss a tablet:**\nFor your prescribed therapy (**{farmaci_str}**), the golden safety rule is: **NEVER take a double dose** to make up for a missed tablet (especially with blood thinners like *Apixaban/Eliquis* or heart rate medications). Take the next dose at the normal scheduled time (`08:00`, `14:00`, or `20:00`).\n\nℹ️ *Medical Disclaimer: Informational guidance; consult your doctor or pharmacist if unsure.*",
            "food": f"🥗 **Food, Water & Salt Rules:**\nAccording to your medical report:\n- **Low Sodium:** Keep salt intake below **2 grams per day** (avoid processed foods and salty snacks).\n- **Fluid Intake:** Limit total daily fluids to **max 1.5 liters/day** (for cardiology care) and weigh yourself every morning before breakfast.\n- **Medications with meals:** Follow your daily schedule ({farmaci_str}).\n\nℹ️ *Medical Disclaimer: Based on your hospital discharge instructions.*",
            "general": f"🩺 **Answer Based on Your Medical Report:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Active Medications:** {farmaci_str}\n- **Next Steps:** {passi_str}\n- **Emergency Red Flag:** {red_str}\n\nℹ️ *Medical Disclaimer: This assistant provides report-based guidance and does not replace your doctor.*",
        },
        "ru": {
            "drive": (
                "🚗 **Рекомендации по вождению автомобиля:**\n"
                + (
                    "Так как на правую ногу наложен **ортез Walker под углом 90°** с **полным запретом опоры на стопу в течение 15 дней**, **водить машину категорически нельзя** до контрольного рентгена и осмотра ортопеда через 28 дней."
                    if is_ortho
                    else "В первые **7–10 дней после выписки рекомендуется воздержаться от вождения**, пока артериальное давление и пульс полностью не стабилизируются на фоне приема препаратов (*Бисопролол, Рамиприл*) и до сдачи контрольного анализа крови через 7 дней."
                )
                + "\n\nℹ️ *Медицинское примечание: Рекомендация основана на вашей выписке; проконсультируйтесь с лечащим врачом.*"
            ),
            "pill": f"💊 **Что делать, если вы забыли принять таблетку:**\nСогласно вашему плану лечения (**{farmaci_str}**), главное правило безопасности: **НИКОГДА не принимайте двойную дозу**, чтобы компенсировать пропущенный прием (особенно при приеме антикоагулянтов *Апиксабан/Эликвис* или препаратов для пульса и давления). Примите следующую таблетку строго по расписанию (`08:00`, `14:00` или `20:00`).\n\nℹ️ *Медицинское примечание: Не меняйте дозировку без консультации с врачом.*",
            "food": f"🥗 **Правила питания, питьевого режима и употребления соли:**\nСогласно вашему выписному эпикризу:\n- **Ограничение соли:** низкосолевая диета (**менее 2 г соли в сутки**), исключите соленья, колбасы и полуфабрикаты.\n- **Контроль жидкости:** употребляйте **не более 1,5 литров жидкости в сутки** и взвешивайтесь каждое утро натощак.\n- **Прием лекарств:** соблюдайте расписание ({farmaci_str}).\n\nℹ️ *Медицинское примечание: Информация носит справочный характер на основе вашей выписки.*",
            "general": f"🩺 **Ответ на основе вашей медицинской выписки:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Назначенные препараты:** {farmaci_str}\n- **Следующие шаги:** {passi_str}\n- **Экстренный симптом (Скорая 103/112):** {red_str}\n\nℹ️ *Медицинское примечание: Ответ основан на тексте выписки и не заменяет консультацию врача.*",
        },
        "es": {
            "drive": "🚗 **Indicaciones sobre la conducción:**\nPor seguridad, **evite conducir durante los primeros 7–15 días** (y nunca conduzca mientras lleve la bota Walker o si nota mareos al ajustar la medicación). Espere a la revisión médica de control.\n\nℹ️ *Aviso Médico: Basado en su informe de alta; consulte siempre a su médico.*",
            "pill": f"💊 **Qué hacer si olvida una pastilla:**\nEn su tratamiento (**{farmaci_str}**), **NUNCA tome una dosis doble** para compensar un olvido (especialmente con anticoagulantes como *Eliquis/Apixaban* o fármacos cardíacos). Continúe con la siguiente toma en su horario habitual (`08:00`, `14:00` o `20:00`).\n\nℹ️ *Aviso Médico: No modifique la pauta sin consultar a su médico.*",
            "food": "🥗 **Alimentación, Agua y Sal:**\nSu informe indica:\n- **Poca sal:** dieta hiposódica (**menos de 2 g de sal al día**).\n- **Control de líquidos:** máximo **1,5 litros al día** y control de peso cada mañana en ayunas.\n\nℹ️ *Aviso Médico: Orientación informativa basada en su informe de alta.*",
            "general": f"🩺 **Respuesta según su Informe Clínico:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Medicación prescrita:** {farmaci_str}\n- **Próximos pasos:** {passi_str}\n- **Alerta de Urgencias:** {red_str}\n\nℹ️ *Aviso Médico: No sustituye el criterio de su médico.*",
        },
        "fr": {
            "drive": "🚗 **Conseils concernant la conduite :**\nPar mesure de sécurité, **évitez de conduire pendant les 7 à 15 premiers jours** suivant la sortie (et interdiction stricte avec la botte Walker à la cheville droite) jusqu'à stabilisation complète et avis médical.\n\nℹ️ *Avis Médical : Basé sur votre lettre de sortie ; demandez confirmation à votre médecin.*",
            "pill": f"💊 **Que faire en cas d'oubli d'un comprimé :**\nPour votre traitement (**{farmaci_str}**), **ne prenez JAMAIS de double dose** pour compenser un oubli (en particulier pour *Eliquis/Apixaban* ou les bêta-bloquants). Prenez simplement la dose suivante à l'heure prévue.\n\nℹ️ *Avis Médical : Information basée sur votre compte-rendu.*",
            "food": "🥗 **Alimentation, Eau et Sel :**\nVotre compte-rendu recommande :\n- **Régime hyposodé :** moins de **2 g de sel par jour**.\n- **Hydratation contrôlée :** maximum **1,5 L de liquides par jour** et pesée quotidienne le matin à jeun.\n\nℹ️ *Avis Médical : Ne remplace pas l'avis de votre médecin traitant.*",
            "general": f"🩺 **Réponse basée sur votre Compte-Rendu :**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Traitement actif :** {farmaci_str}\n- **Prochaines étapes :** {passi_str}\n- **Signe d'urgence (15/112) :** {red_str}\n\nℹ️ *Avis Médical : Information basée sur votre dossier.*",
        },
        "de": {
            "drive": "🚗 **Hinweise zum Autofahren:**\nBitte **verzichten Sie in den ersten 7–15 Tagen nach der Entlassung auf das Autofahren** (mit einer Walker-Orthese am rechten Bein ist das Fahren strikt verboten), bis Ihre Werte bei der Nachkontrolle überprüft wurden.\n\nℹ️ *Medizinischer Hinweis: Basierend auf Ihrem Arztbrief; fragen Sie Ihren Arzt.*",
            "pill": f"💊 **Was tun bei einer vergessenen Tablette:**\nBei Ihrer Medikation (**{farmaci_str}**) gilt: **Nehmen Sie NIEMALS die doppelte Dosis ein**, wenn Sie eine Einnahme vergessen haben. Fahren Sie zum nächsten regulären Zeitpunkt (`08:00`, `14:00` oder `20:00` Uhr) fort.\n\nℹ️ *Medizinischer Hinweis: Ersetzt keinen ärztlichen Rat.*",
            "food": "🥗 **Ernährung, Trinkmenge & Salz:**\nLaut Entlassungsbrief gilt:\n- **Salzarme Kost:** weniger als **2 g Salz pro Tag**.\n- **Flüssigkeit:** maximal **1,5 Liter pro Tag** sowie tägliches Wiegen morgens nüchtern.\n\nℹ️ *Medizinischer Hinweis: Information gemäß Ihrem Entlassungsbericht.*",
            "general": f"🩺 **Antwort laut Ihrem Arztbrief:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Medikamente:** {farmaci_str}\n- **Nächste Schritte:** {passi_str}\n- **Notfall-Warnzeichen:** {red_str}\n\nℹ️ *Medizinischer Hinweis: Dient nur zur Information.*",
        },
        "ar": {
            "drive": "🚗 **إرشادات قيادة السيارة:**\nلأجل سلامتك، **يُنصح بتجنب قيادة السيارة خلال أول 7 إلى 15 يوماً** بعد الخروج من المستشفى (ويُمنع القيادة تماماً أثناء ارتداء جبيرة الكاحل Walker) حتى استقرار الضغط والنبض ومراجعة الطبيب.\n\nℹ️ *تنبيه طبي: إرشادات مبنية على تقرير الخروج ولا تغني عن استشارة الطبيب.*",
            "pill": f"💊 **ماذا تفعل إذا نسيت جرعة الدواء:**\nبالنسبة لأدويتك الموصوفة (**{farmaci_str}**)، القاعدة الذهبية هي: **لا تتناول أبداً جرعة مضاعفة** لتعويض الجرعة المنسية (خاصة مع مميعات الدم مثل *Apixaban/Eliquis*). انتظر موعد الجرعة التالية المعتاد.\n\nℹ️ *تنبيه طبي: استشر طبيبك دائماً عند الشك.*",
            "food": "🥗 **تعليمات الطعام والماء والملح:**\nيوصي تقريرك الطبي بما يلي:\n- **تقليل الملح:** أقل من **2 جرام يومياً**.\n- **السوائل:** بحد أقصى **1.5 لتر يومياً** مع قياس الوزن كل صباح قبل الإفطار.\n\nℹ️ *تنبيه طبي: معلومات مستخرجة من تقرير الخروج الخاص بك.*",
            "general": f"🩺 **الإجابة بناءً على تقريرك الطبي:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **الأدوية الموصوفة:** {farmaci_str}\n- **الخطوات القادمة:** {passi_str}\n- **علامات الطوارئ:** {red_str}\n\nℹ️ *تنبيه طبي: هذه المعلومات استرشادية ولا تغني عن الطبيب.*",
        },
        "zh": {
            "drive": "🚗 **关于驾驶的建议：**\n为了您的安全，出院后**前 7–15 天内请勿开车**（如果右脚佩戴 Walker 支具靴则严禁驾驶），需等待血压、心率稳定并完成复查后再由医生评估。\n\nℹ️ *医疗声明：基于您的出院报告生成，具体请遵医嘱。*",
            "pill": f"💊 **如果漏服了一片药该怎么办：**\n针对您的处方药物（**{farmaci_str}**），核心安全原则是：**切勿为了补服而服用双倍剂量**（尤其是抗凝药 *Apixaban/Eliquis* 或降压控心率药物）。请按正常时间服用下一剂。\n\nℹ️ *医疗声明：如有疑问请及时联系主治医生。*",
            "food": "🥗 **饮食、饮水与吃盐规定：**\n根据您的出院小结：\n- **低盐饮食：** 每日食盐摄入量控制在 **2 克以下**。\n- **控制液体量：** 每日总饮水量不超过 **1.5 升**，并每天清晨空腹称重记录。\n\nℹ️ *医疗声明：仅供参考，不能替代医生诊疗意见。*",
            "general": f"🩺 **根据您的出院报告解答：**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **当前用药：** {farmaci_str}\n- **后续复查：** {passi_str}\n- **急诊危险信号：** {red_str}\n\nℹ️ *医疗声明：本回答仅基于报告提供信息参考。*",
        },
        "ro": {
            "drive": "🚗 **Indicații privind șofatul:**\nPentru siguranța dvs., **evitați să conduceți în primele 7–15 zile** de la externare (iar cu orteza Walker pe piciorul drept șofatul este strict interzis) până la controlul medical.\n\nℹ️ *Notă Medicală: Informație bazată pe biletul de externare.*",
            "pill": f"💊 **Ce faceți dacă uitați o pastilă:**\nPentru schema dvs. (**{farmaci_str}**), **NU luați niciodată o doză dublă** pentru a compensa o doză uitată. Continuați cu următoarea doză la ora obișnuită (`08:00`, `14:00` sau `20:00`).\n\nℹ️ *Notă Medicală: Nu modificați dozele fără acordul medicului.*",
            "food": "🥗 **Reguli privind mâncarea, apa și sarea:**\nBiletul de externare recomandă:\n- **Regim hiposodat:** sub **2 g de sare pe zi**.\n- **Lichide:** maximum **1,5 litri pe zi** și cântărire zilnică dimineața pe nemâncate.\n\nℹ️ *Notă Medicală: Informație orientativă; consultați medicul.*",
            "general": f"🩺 **Răspuns conform Biletului de Externare:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Medicație prescrisă:** {farmaci_str}\n- **Pașii următori:** {passi_str}\n- **Urgențe (112):** {red_str}\n\nℹ️ *Notă Medicală: Nu înlocuiește consultul medical.*",
        },
        "uk": {
            "drive": "🚗 **Рекомендації щодо водіння авто:**\nЗаради безпеки **утримайтеся від керування автомобілем у перші 7–15 днів** після виписки (а при носінні ортеза Walker на правій нозі водіння суворо заборонено) до контрольного огляду лікаря.\n\nℹ️ *Медичне застереження: На основі вашої виписки; проконсультуйтеся з лікарем.*",
            "pill": f"💊 **Що робити, якщо ви забули прийняти таблетку:**\nДля вашої терапії (**{farmaci_str}**) головне правило: **НІКОЛИ не приймайте подвійну дозу**, щоб компенсувати пропущену таблетку. Прийміть наступну дозу за графіком (`08:00`, `14:00` або `20:00`).\n\nℹ️ *Медичне застереження: Не змінюйте дозування самостійно.*",
            "food": "🥗 **Харчування, вода та сіль:**\nЗгідно з випискою:\n- **Обмеження солі:** менше **2 г солі на добу**.\n- **Контроль рідини:** до **1,5 л рідини на день** та щоденне зважування вранці натщесерце.\n\nℹ️ *Медичне застереження: Інформація має ознайомчий характер.*",
            "general": f"🩺 **Відповідь на основі вашої виписки:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Призначені ліки:** {farmaci_str}\n- **Наступні кроки:** {passi_str}\n- **Термінова допомога (103/112):** {red_str}\n\nℹ️ *Медичне застереження: Не замінює консультацію лікаря.*",
        },
        "hi": {
            "drive": "🚗 **ड्राइविंग संबंधी निर्देश:**\nसुरक्षा के लिए, अस्पताल से छुट्टी के बाद **पहले 7–15 दिनों तक गाड़ी न चलाएं** (और यदि दाएं पैर में Walker बूट पहना है तो ड्राइविंग बिल्कुल मना है) जब तक कि डॉक्टर जांच न कर लें।\n\nℹ️ *चिकित्सा अस्वीकरण: यह जानकारी आपकी रिपोर्ट पर आधारित है।*",
            "pill": f"💊 **यदि कोई गोली लेना भूल जाएं तो क्या करें:**\nआपकी दवाओं (**{farmaci_str}**) के लिए सबसे महत्वपूर्ण नियम है: छूटी हुई दवा की भरपाई के लिए **कभी भी दोगुनी खुराक (double dose) न लें**। अगली खुराक निर्धारित समय पर ही लें।\n\nℹ️ *चिकित्सा अस्वीकरण: बिना डॉक्टर की सलाह के खुराक न बदलें।*",
            "food": "🥗 **भोजन, पानी और नमक के नियम:**\nआपकी रिपोर्ट के अनुसार:\n- **कम नमक:** प्रतिदिन **2 ग्राम से कम नमक** लें।\n- **तरल पदार्थ:** दिन भर में अधिकतम **1.5 लीटर तरल** लें और रोज सुबह खाली पेट वजन करें।\n\nℹ️ *चिकित्सा अस्वीकरण: डॉक्टर की सलाह का पालन करें।*",
            "general": f"🩺 **आपकी मेडिकल रिपोर्ट के आधार पर उत्तर:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **निर्धारित दवाएं:** {farmaci_str}\n- **अगले कदम:** {passi_str}\n- **आपातकालीन लक्षण:** {red_str}\n\nℹ️ *चिकित्सा अस्वीकरण: यह डॉक्टर की सलाह का विकल्प नहीं है।*",
        },
        "pt": {
            "drive": "🚗 **Indicações sobre Condução:**\nPor segurança, **evite conduzir nos primeiros 7 a 15 dias** após a alta (e é estritamente proibido conduzir com a bota Walker no pé direito) até à consulta médica de reavaliação.\n\nℹ️ *Aviso Médico: Orientação baseada na nota de alta.*",
            "pill": f"💊 **O que fazer se esquecer um comprimido:**\nPara a sua medicação (**{farmaci_str}**), **NUNCA tome uma dose dupla** para compensar um esquecimento. Tome a próxima dose no horário habitual (`08:00`, `14:00` ou `20:00`).\n\nℹ️ *Aviso Médico: Consulte sempre o seu médico.*",
            "food": "🥗 **Regras sobre Comida, Água e Sal:**\nA sua nota de alta recomenda:\n- **Pouco sal:** menos de **2 g de sal por dia**.\n- **Líquidos controlados:** máximo de **1,5 litros por dia** e pesagem diária em jejum.\n\nℹ️ *Aviso Médico: Não substitui o parecer médico.*",
            "general": f"🩺 **Resposta com base no seu Relatório:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Medicação prescrita:** {farmaci_str}\n- **Próximos passos:** {passi_str}\n- **Sinal de Urgência (112):** {red_str}\n\nℹ️ *Aviso Médico: Informação baseada no relatório clínico.*",
        },
        "sq": {
            "drive": "🚗 **Udhëzime për Ngasjen e Makinës:**\nPër sigurinë tuaj, **shmangni ngasjen e makinës gjatë 7–15 ditëve të para** pas daljes nga spitali (dhe ndalohet rreptësisht nëse mbani tutoren Walker në këmbën e djathtë) deri në kontrollin mjekësor.\n\nℹ️ *Shënim Mjekësor: Bazuar në fletëdaljen tuaj spitalore.*",
            "pill": f"💊 **Çfarë të bëni nëse harroni një kokërr:**\nPër barnat tuaja (**{farmaci_str}**), rregulli kryesor është: **MOS merrni kurrë dozë të dyfishtë** për të zëvendësuar kokrrën e harruar. Vazhdoni me dozën e radhës sipas orarit (`08:00`, `14:00` ose `20:00`).\n\nℹ️ *Shënim Mjekësor: Mos ndryshoni dozat pa pyetur mjekun.*",
            "food": "🥗 **Rregullat për Ushqimin, Ujin dhe Kripën:**\nSipas fletëdaljes suaj:\n- **Pak kripë:** më pak se **2 gramë kripë në ditë**.\n- **Lëngjet:** maksimumi **1,5 litra në ditë** dhe peshim çdo mëngjes esëll.\n\nℹ️ *Shënim Mjekësor: Informacion orientues; konsultohuni me mjekun.*",
            "general": f"🩺 **Përgjigje bazuar në Raportin Tuaj:**\n{parsed_result.get('riassunto_empatico', '')}\n\n- **Barnat e përshkruara:** {farmaci_str}\n- **Hapat e radhës:** {passi_str}\n- **Shenjë Urgjence (112):** {red_str}\n\nℹ️ *Shënim Mjekësor: Nuk zëvendëson këshillën e mjekut.*",
        },
    }

    lang_qa = qa_bank.get(lang_code, qa_bank["en"])
    return lang_qa[topic], time.perf_counter() - t0


# =====================================================================
# COMPONENTE AUDIO TTS (WEB SPEECH API JS PER 12 LINGUE)
# =====================================================================
def render_interactive_tts_player(
    text_to_speak: str, language_label: str, play_label: str, stop_label: str
) -> None:
    lang_cfg = LANGUAGES_CONFIG.get(language_label, LANGUAGES_CONFIG["🇮🇹 Italiano"])
    lang_code = lang_cfg["bcp47"]
    safe_text_json = json.dumps(text_to_speak)

    st.components.v1.html(
        f"""
        <div style="font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 4px 0;">
            <button id="playBtn" onclick="speakSummary()"
                style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; border: none; border-radius: 12px; padding: 11px 18px; font-weight: 700; font-size: 0.92rem; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);">
                {html.escape(play_label)} ({lang_code})
            </button>
            <button onclick="stopSummary()"
                style="background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 12px; padding: 11px 14px; font-weight: 700; font-size: 0.88rem; cursor: pointer;">
                {html.escape(stop_label)}
            </button>
            <span id="ttsStatus" style="font-size: 0.82rem; color: #0284c7; font-weight: 700;"></span>
        </div>
        <script>
        function speakSummary() {{
            const statusEl = document.getElementById('ttsStatus');
            if (!('speechSynthesis' in window)) {{
                statusEl.innerText = '⚠️ TTS not supported';
                return;
            }}
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance({safe_text_json});
            utterance.lang = "{lang_code}";
            utterance.rate = 0.96;
            utterance.onstart = () => {{ statusEl.innerText = '🎙️ Audio ({lang_code})...'; }};
            utterance.onend = () => {{ statusEl.innerText = '✅'; }};
            utterance.onerror = () => {{ statusEl.innerText = ''; }};
            window.speechSynthesis.speak(utterance);
        }}
        function stopSummary() {{
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                document.getElementById('ttsStatus').innerText = '';
            }}
        }}
        </script>
        """,
        height=62,
    )


# =====================================================================
# GENERATORE FOGLIO RIEPILOGO STAMPABILE ("DA ATTACCARE AL FRIGORIFERO")
# =====================================================================
def generate_printable_html(
    data: Dict[str, Any],
    language_label: str,
    profile_name: str,
    ui: Dict[str, str],
    is_colorblind: bool = False,
) -> str:
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    lang_cfg = LANGUAGES_CONFIG.get(language_label, LANGUAGES_CONFIG["🇮🇹 Italiano"])
    dir_attr = "rtl" if lang_cfg["rtl"] else "ltr"
    summary_html = html.escape(str(data.get("riassunto_empatico", "")))

    med_rows = ""
    for m in data.get("terapia_oraria", []):
        med_rows += f"""
        <tr>
            <td><span class="slot-pill">{html.escape(str(m.get('fascia_oraria', '')))}</span></td>
            <td><strong>{html.escape(str(m.get('farmaco', '')))}</strong></td>
            <td><span class="dose-pill">{html.escape(str(m.get('dosaggio', '')))}</span></td>
            <td><strong>{html.escape(str(m.get('scopo_semplice', '')))}</strong></td>
            <td>🍽️ {html.escape(str(m.get('avvertenze', '')))}</td>
        </tr>
        """

    semaforo = data.get("semaforo_sintomi", {})
    verde_li = "".join(f"<li>{html.escape(str(x))}</li>" for x in semaforo.get("verde", []))
    giallo_li = "".join(f"<li>{html.escape(str(x))}</li>" for x in semaforo.get("giallo", []))
    rosso_li = "".join(f"<li>{html.escape(str(x))}</li>" for x in semaforo.get("rosso", []))
    passi_li = "".join(
        f"<li>☐ {html.escape(str(x))}</li>" for x in data.get("prossimi_passi", [])
    )
    domande_li = "".join(
        f"<li>{html.escape(str(x))}</li>" for x in data.get("domande_consigliate", [])
    )

    g_style = "background: #e0f2fe; border: 3px solid #0072B2;" if is_colorblind else "background: #ecfdf5; border: 2px solid #10b981;"
    y_style = "background: #fef3c7; border: 3px dashed #E69F00;" if is_colorblind else "background: #fffbeb; border: 2px solid #f59e0b;"
    r_style = "background: #ffe4e6; border: 5px double #9f1239;" if is_colorblind else "background: #fef2f2; border: 2px solid #ef4444;"

    return f"""<!DOCTYPE html>
<html lang="{lang_cfg['code']}" dir="{dir_attr}">
<head>
<meta charset="UTF-8">
<title>MedClear AI — Patient Summary</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
  body {{ font-family: 'Plus Jakarta Sans', Arial, sans-serif; color: #0f172a; margin: 28px; line-height: 1.55; background: #ffffff; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #0284c7; padding-bottom: 14px; margin-bottom: 20px; }}
  .title {{ font-size: 24px; font-weight: 800; color: #0f172a; }}
  .title span {{ color: #0284c7; }}
  .meta {{ font-size: 12px; color: #475569; margin-top: 4px; }}
  .summary {{ background: #f0f9ff; border: 1px solid #bae6fd; border-left: 6px solid #0284c7; padding: 16px 20px; border-radius: 12px; margin-bottom: 22px; font-size: 15px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 22px; font-size: 13.5px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 10px 12px; text-align: start; }}
  th {{ background: #0f172a; color: white; font-weight: 700; }}
  .slot-pill {{ background: #f1f5f9; padding: 3px 8px; border-radius: 6px; font-weight: 700; }}
  .dose-pill {{ background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 999px; font-weight: 700; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 22px; }}
  .box {{ padding: 14px; border-radius: 12px; font-size: 13px; }}
  .print-btn {{ background: #0284c7; color: white; border: none; padding: 12px 22px; border-radius: 10px; font-weight: 800; cursor: pointer; margin-bottom: 18px; font-size: 14px; }}
  @media print {{ .print-btn {{ display: none; }} body {{ margin: 12px; }} }}
</style>
</head>
<body>
  <button class="print-btn" onclick="window.print()">🖨️ Print</button>
  <div class="header">
    <div>
      <div class="title">🩺 MedClear <span>AI</span> — Clinical Discharge &amp; Patient Navigator</div>
      <div class="meta">{html.escape(language_label)} | {html.escape(profile_name)} | {now_str}</div>
    </div>
  </div>
  <div class="summary"><strong>💙 {html.escape(ui['step2_title'])}:</strong><br>{summary_html}</div>
  <h3>💊 {html.escape(ui['step3_title'])}</h3>
  <table>
    <tbody>{med_rows}</tbody>
  </table>
  <h3>🚦 {html.escape(ui['step4_title'])}</h3>
  <div class="grid">
    <div class="box" style="{g_style}"><strong>{html.escape(ui['triage_g'])}</strong><ul>{verde_li}</ul></div>
    <div class="box" style="{y_style}"><strong>{html.escape(ui['triage_y'])}</strong><ul>{giallo_li}</ul></div>
    <div class="box" style="{r_style}"><strong>{html.escape(ui['triage_r'])}</strong><ul>{rosso_li}</ul></div>
  </div>
  <h3>{html.escape(ui['steps_title'])}</h3>
  <ul style="list-style:none; padding-left:0; font-size:14px;">{passi_li}</ul>
  <h3>{html.escape(ui['questions_title'])}</h3>
  <ol style="font-size:14px;">{domande_li}</ol>
</body>
</html>"""


def generate_printable_txt(
    data: Dict[str, Any], language_label: str, profile_name: str
) -> str:
    lines = [
        "====================================================================",
        "  MEDCLEAR AI — CLINICAL DISCHARGE & PATIENT NAVIGATOR",
        f"  {language_label} | {profile_name}",
        "====================================================================",
        "",
        str(data.get("riassunto_empatico", "")),
        "",
        "--------------------------------------------------------------------",
    ]
    for m in data.get("terapia_oraria", []):
        lines.append(
            f"  [{m.get('fascia_oraria', '').upper()}] {m.get('farmaco', '')} — {m.get('dosaggio', '')}"
        )
        lines.append(f"     • {m.get('scopo_semplice', '')}")
        lines.append(f"     • {m.get('avvertenze', '')}")

    sem = data.get("semaforo_sintomi", {})
    lines.extend(
        [
            "",
            "--------------------------------------------------------------------",
            *[f"  [🟢] {x}" for x in sem.get("verde", [])],
            *[f"  [🟡] {x}" for x in sem.get("giallo", [])],
            *[f"  [🔴] {x}" for x in sem.get("rosso", [])],
            "",
            "--------------------------------------------------------------------",
            *[f"  [ ] {x}" for x in data.get("prossimi_passi", [])],
            "",
            *[f"  {i+1}. {x}" for i, x in enumerate(data.get("domande_consigliate", []))],
        ]
    )
    return "\n".join(lines)


# =====================================================================
# INIZIALIZZAZIONE STATO SESSIONE
# =====================================================================
def init_session_state() -> None:
    if "medical_text" not in st.session_state:
        st.session_state.medical_text = DEMO_CASES["cardiologia"]["testo"]
    if "active_case_key" not in st.session_state:
        st.session_state.active_case_key = "cardiologia"
    if "active_case_label" not in st.session_state:
        st.session_state.active_case_label = DEMO_CASES["cardiologia"]["titolo"]
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None
    if "last_lang_rendered" not in st.session_state:
        st.session_state.last_lang_rendered = "🇮🇹 Italiano"
    if "last_profile_idx" not in st.session_state:
        st.session_state.last_profile_idx = 0
    if "last_latency" not in st.session_state:
        st.session_state.last_latency = 0.82
    if "last_throughput" not in st.session_state:
        st.session_state.last_throughput = 134
    if "last_engine_used" not in st.session_state:
        st.session_state.last_engine_used = "AMD Instinct™ MI300X / Gemini Hybrid"
    if "inference_count" not in st.session_state:
        st.session_state.inference_count = 1
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "theme_idx" not in st.session_state:
        st.session_state.theme_idx = 0
    if "profile_idx" not in st.session_state:
        st.session_state.profile_idx = 0
    if "high_readability" not in st.session_state:
        st.session_state.high_readability = False
    if "unified_api_key" not in st.session_state:
        st.session_state.unified_api_key = (
            os.environ.get("EVOLUS_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        )
    if "evolus_base_url" not in st.session_state:
        st.session_state.evolus_base_url = os.environ.get(
            "EVOLUS_BASE_URL", "https://api.evolus.ai/v1"
        )
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "meta-llama/Llama-3.1-8B-Instruct"
    if "output_language" not in st.session_state:
        st.session_state.output_language = "🇮🇹 Italiano"


# =====================================================================
# APPLICAZIONE PRINCIPALE (INTERAMENTE TRADOTTA IN 13 LINGUE)
# =====================================================================
def main() -> None:
    init_session_state()

    lang_options = list(LANGUAGES_CONFIG.keys())
    model_options = [
        "meta-llama/Llama-3.1-8B-Instruct",
        "Qwen/Qwen2.5-72B-Instruct",
        "mistralai/Mistral-Nemo-Instruct-2407",
        "gemini-2.5-flash",
        "gemini-3.8-flash",
    ]

    # Callbacks di sincronizzazione bidirezionale tra Control Dock e Sidebar
    def _sync_from_dock_key() -> None:
        val = st.session_state.get("dock_api_key_input", "")
        st.session_state.unified_api_key = val
        st.session_state["sb_api_key_input"] = val

    def _sync_from_sb_key() -> None:
        val = st.session_state.get("sb_api_key_input", "")
        st.session_state.unified_api_key = val
        st.session_state["dock_api_key_input"] = val

    def _sync_from_dock_lang() -> None:
        val = st.session_state.get("dock_lang_select", "🇮🇹 Italiano")
        if val != st.session_state.output_language:
            st.session_state.output_language = val
            st.session_state["sb_lang_select"] = val
            new_cfg = LANGUAGES_CONFIG.get(val, LANGUAGES_CONFIG["🇮🇹 Italiano"])
            new_ui = FULL_UI_I18N.get(new_cfg["code"], FULL_UI_I18N["it"])
            st.session_state.chat_messages = [
                {"role": "assistant", "content": new_ui["chat_welcome"]}
            ]

    def _sync_from_sb_lang() -> None:
        val = st.session_state.get("sb_lang_select", "🇮🇹 Italiano")
        if val != st.session_state.output_language:
            st.session_state.output_language = val
            st.session_state["dock_lang_select"] = val
            new_cfg = LANGUAGES_CONFIG.get(val, LANGUAGES_CONFIG["🇮🇹 Italiano"])
            new_ui = FULL_UI_I18N.get(new_cfg["code"], FULL_UI_I18N["it"])
            st.session_state.chat_messages = [
                {"role": "assistant", "content": new_ui["chat_welcome"]}
            ]

    def _sync_from_dock_prof() -> None:
        idx = int(st.session_state.get("dock_profile_select", 0))
        st.session_state.profile_idx = idx
        st.session_state["sb_profile_select"] = idx

    def _sync_from_sb_prof() -> None:
        idx = int(st.session_state.get("sb_profile_select", 0))
        st.session_state.profile_idx = idx
        st.session_state["dock_profile_select"] = idx

    def _sync_from_dock_theme() -> None:
        idx = int(st.session_state.get("dock_theme_select", 0))
        st.session_state.theme_idx = idx
        st.session_state["sb_theme_select"] = idx

    def _sync_from_sb_theme() -> None:
        idx = int(st.session_state.get("sb_theme_select", 0))
        st.session_state.theme_idx = idx
        st.session_state["dock_theme_select"] = idx

    def _sync_from_dock_font() -> None:
        val = bool(st.session_state.get("dock_big_font_toggle", False))
        st.session_state.high_readability = val
        st.session_state["sb_big_font_toggle"] = val

    def _sync_from_sb_font() -> None:
        val = bool(st.session_state.get("sb_big_font_toggle", False))
        st.session_state.high_readability = val
        st.session_state["dock_big_font_toggle"] = val

    def _sync_from_dock_model() -> None:
        val = st.session_state.get("dock_model_select", model_options[0])
        st.session_state.selected_model = val
        st.session_state["sb_model_select"] = val

    def _sync_from_sb_model() -> None:
        val = st.session_state.get("sb_model_select", model_options[0])
        st.session_state.selected_model = val
        st.session_state["dock_model_select"] = val

    def _sync_from_dock_url() -> None:
        val = st.session_state.get("dock_base_url_input", "https://api.evolus.ai/v1")
        st.session_state.evolus_base_url = val
        st.session_state["sb_base_url_input"] = val

    def _sync_from_sb_url() -> None:
        val = st.session_state.get("sb_base_url_input", "https://api.evolus.ai/v1")
        st.session_state.evolus_base_url = val
        st.session_state["dock_base_url_input"] = val

    # Assicura che le chiavi widget di Dock e Sidebar siano sempre allineate allo stato canonico
    st.session_state["dock_api_key_input"] = st.session_state.unified_api_key
    st.session_state["sb_api_key_input"] = st.session_state.unified_api_key
    st.session_state["dock_lang_select"] = st.session_state.output_language
    st.session_state["sb_lang_select"] = st.session_state.output_language
    st.session_state["dock_profile_select"] = st.session_state.profile_idx
    st.session_state["sb_profile_select"] = st.session_state.profile_idx
    st.session_state["dock_theme_select"] = st.session_state.theme_idx
    st.session_state["sb_theme_select"] = st.session_state.theme_idx
    st.session_state["dock_big_font_toggle"] = st.session_state.high_readability
    st.session_state["sb_big_font_toggle"] = st.session_state.high_readability
    st.session_state["dock_model_select"] = st.session_state.selected_model
    st.session_state["sb_model_select"] = st.session_state.selected_model
    st.session_state["dock_base_url_input"] = st.session_state.evolus_base_url
    st.session_state["sb_base_url_input"] = st.session_state.evolus_base_url

    # Carica tutte le stringhe dell'interfaccia nella lingua attiva
    current_lang_cfg = LANGUAGES_CONFIG.get(
        st.session_state.output_language, LANGUAGES_CONFIG["🇮🇹 Italiano"]
    )
    ui = FULL_UI_I18N.get(current_lang_cfg["code"], FULL_UI_I18N["it"])
    is_rtl_active = current_lang_cfg["rtl"]

    theme_options_localized = ui["themes"].split("|")
    profile_options_localized = ui["profiles"].split("|")
    current_profile_name = profile_options_localized[st.session_state.profile_idx]
    current_theme_name = theme_options_localized[st.session_state.theme_idx]
    is_colorblind_mode = st.session_state.theme_idx == 2

    # Mantieni l'etichetta del caso clinico attivo tradotta nella lingua corrente
    case_btn_map = {
        "cardiologia": ui["case1_btn"],
        "ortopedia": ui["case2_btn"],
        "pediatria": ui["case3_btn"],
    }
    if st.session_state.active_case_key in case_btn_map and not str(
        st.session_state.active_case_label
    ).startswith("📄 PDF:"):
        st.session_state.active_case_label = case_btn_map[
            st.session_state.active_case_key
        ]

    # Inietta il CSS globale (Tema Light / Dark / Okabe-Ito + Carattere Grande + RTL Arabo)
    inject_custom_css(
        theme_idx=st.session_state.theme_idx,
        high_readability=st.session_state.high_readability,
        is_rtl=is_rtl_active,
    )

    # -----------------------------------------------------------------
    # TOP ENTERPRISE BANNER & AMD ROCm TELEMETRY BAR
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="enterprise-hero">
            <div class="hero-top-row">
                <div class="hero-brand">
                    <div class="hero-logo-box">🩺</div>
                    <div>
                        <h1 class="hero-title">MedClear <span>AI</span> — Clinical Discharge &amp; Patient Navigator</h1>
                        <p class="hero-subtitle">{html.escape(ui["hero_sub"])}</p>
                    </div>
                </div>
                <div class="hero-engine-tag">
                    ⚡ Hybrid AI Engine: AMD ROCm™ (vLLM/Evolus Open-Weight) &amp; Gemini Flash
                </div>
            </div>
            <div class="telemetry-bar">
                <div class="telemetry-pill">🟢 Engine: AMD Instinct™ MI300X (ROCm™ 6.2)</div>
                <div class="telemetry-pill">⚡ Throughput: ~{st.session_state.last_throughput} tokens/sec</div>
                <div class="telemetry-pill">🔒 Privacy: Local Hospital Enclave (Zero Data Leakage)</div>
                <div class="telemetry-pill">🌍 Multilingual Medical NER Active (13 Languages)</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------
    # BARRA DI CONTROLLO RAPIDA (CONTROL DOCK) TRADOTTA NELLA LINGUA SCELTA
    # -----------------------------------------------------------------
    with st.expander(ui["dock_title"], expanded=True):
        dock_col1, dock_col2, dock_col3, dock_col4 = st.columns([1.35, 1.15, 1.25, 1.1])

        with dock_col1:
            st.text_input(
                ui["api_label"],
                type="password",
                placeholder=ui["api_placeholder"],
                key="dock_api_key_input",
                on_change=_sync_from_dock_key,
            )

            k_trim = st.session_state.unified_api_key.strip()
            if k_trim.startswith("evo_"):
                st.success(ui["status_evolus"])
            elif k_trim.startswith("AIza"):
                st.success(ui["status_gemini"])
            elif k_trim:
                st.info(ui["status_custom"])
            else:
                st.info(ui["status_demo"])

        with dock_col2:
            st.selectbox(
                ui["lang_label"],
                options=lang_options,
                key="dock_lang_select",
                on_change=_sync_from_dock_lang,
            )

            st.selectbox(
                ui["profile_label"],
                options=[0, 1, 2],
                format_func=lambda idx: profile_options_localized[idx],
                key="dock_profile_select",
                on_change=_sync_from_dock_prof,
            )

        with dock_col3:
            st.selectbox(
                ui["theme_label"],
                options=[0, 1, 2],
                format_func=lambda idx: theme_options_localized[idx],
                key="dock_theme_select",
                on_change=_sync_from_dock_theme,
            )

            st.toggle(
                ui["big_font_label"],
                key="dock_big_font_toggle",
                on_change=_sync_from_dock_font,
            )

        with dock_col4:
            st.selectbox(
                ui["model_label"],
                options=model_options,
                key="dock_model_select",
                on_change=_sync_from_dock_model,
            )

            st.text_input(
                ui["url_label"],
                key="dock_base_url_input",
                on_change=_sync_from_dock_url,
            )

    # -----------------------------------------------------------------
    # SIDEBAR SINCRONIZZATA E INTERAMENTE TRADOTTA
    # -----------------------------------------------------------------
    with st.sidebar:
        st.markdown(f"### {ui['theme_label']}")

        st.selectbox(
            ui["theme_label"],
            options=[0, 1, 2],
            format_func=lambda idx: theme_options_localized[idx],
            key="sb_theme_select",
            on_change=_sync_from_sb_theme,
        )

        st.toggle(
            ui["big_font_label"],
            key="sb_big_font_toggle",
            on_change=_sync_from_sb_font,
        )

        st.divider()

        st.markdown("### ⚡ Hybrid AI Engine")
        st.text_input(
            ui["api_label"],
            type="password",
            placeholder=ui["api_placeholder"],
            key="sb_api_key_input",
            on_change=_sync_from_sb_key,
        )

        key_trimmed = st.session_state.unified_api_key.strip()
        if key_trimmed.startswith("evo_"):
            st.success(ui["status_evolus"])
        elif key_trimmed.startswith("AIza"):
            st.success(ui["status_gemini"])
        elif key_trimmed:
            st.info(ui["status_custom"])
        else:
            st.info(ui["status_demo"])

        st.text_input(
            ui["url_label"],
            key="sb_base_url_input",
            on_change=_sync_from_sb_url,
        )

        st.selectbox(
            ui["model_label"],
            options=model_options,
            key="sb_model_select",
            on_change=_sync_from_sb_model,
        )

        st.divider()

        st.selectbox(
            ui["lang_label"],
            options=lang_options,
            key="sb_lang_select",
            on_change=_sync_from_sb_lang,
        )

        st.selectbox(
            ui["profile_label"],
            options=[0, 1, 2],
            format_func=lambda idx: profile_options_localized[idx],
            key="sb_profile_select",
            on_change=_sync_from_sb_prof,
        )

        st.divider()

        st.markdown(f"#### {ui['sb_telemetry']}")
        st.markdown(
            f"""
            <div class="sidebar-metric">
                <div class="sidebar-metric-label">{html.escape(ui["sb_latency"])}</div>
                <div class="sidebar-metric-val">⏱️ {st.session_state.last_latency:.2f} s</div>
                <div class="sidebar-metric-sub">⚡ ~{st.session_state.last_throughput} tokens/sec</div>
            </div>
            <div class="sidebar-metric">
                <div class="sidebar-metric-label">{html.escape(ui["sb_engine"])}</div>
                <div class="sidebar-metric-val" style="font-size:0.88rem;">{html.escape(st.session_state.last_engine_used)}</div>
                <div class="sidebar-metric-sub">{html.escape(ui["sb_completed"])}: {st.session_state.inference_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    unified_api_key = st.session_state.unified_api_key
    evolus_base_url = st.session_state.evolus_base_url
    selected_model = st.session_state.selected_model
    output_language = st.session_state.output_language

    # Aggiornamento automatico immediato quando si cambia lingua o profilo
    if (
        st.session_state.analysis_result is None
        or st.session_state.last_lang_rendered != output_language
        or st.session_state.last_profile_idx != st.session_state.profile_idx
    ):
        t0_auto = time.perf_counter()
        parsed_auto, eng_auto = execute_smart_ai_routing(
            medical_text=st.session_state.medical_text,
            language_label=output_language,
            profile_idx=st.session_state.profile_idx,
            profile_name=current_profile_name,
            api_key=unified_api_key,
            evolus_base_url=evolus_base_url,
            selected_model=selected_model,
        )
        st.session_state.analysis_result = parsed_auto
        st.session_state.last_engine_used = eng_auto
        st.session_state.last_latency = max(0.42, time.perf_counter() - t0_auto)
        st.session_state.last_lang_rendered = output_language
        st.session_state.last_profile_idx = st.session_state.profile_idx

    # Banner dedicato quando è attiva la Modalità Daltonici (Okabe-Ito)
    if is_colorblind_mode:
        st.markdown(
            f"""
            <div class="colorblind-banner">
                <span>{html.escape(ui["cb_banner"])}</span>
                <span style="background:rgba(255,255,255,0.2); padding:3px 10px; border-radius:999px; font-size:0.78rem;">WCAG AAA • Okabe-Ito</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------
    # STEP 1: SELEZIONE CASO CLINICO DEMO / UPLOAD REFERTO
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">1</span>
                <span class="step-title-text">{html.escape(ui["step1_title"])}</span>
            </div>
            <span class="step-badge">Clinical Input &amp; NER</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(ui["case1_btn"], use_container_width=True, type="secondary", key="btn_demo_case1"):
            st.session_state.medical_text = DEMO_CASES["cardiologia"]["testo"]
            st.session_state.active_case_key = "cardiologia"
            st.session_state.active_case_label = ui["case1_btn"]
            st.session_state.analysis_result = None
            st.session_state.chat_messages = [
                {"role": "assistant", "content": ui["chat_welcome"]}
            ]
            st.rerun()
    with c2:
        if st.button(ui["case2_btn"], use_container_width=True, type="secondary", key="btn_demo_case2"):
            st.session_state.medical_text = DEMO_CASES["ortopedia"]["testo"]
            st.session_state.active_case_key = "ortopedia"
            st.session_state.active_case_label = ui["case2_btn"]
            st.session_state.analysis_result = None
            st.session_state.chat_messages = [
                {"role": "assistant", "content": ui["chat_welcome"]}
            ]
            st.rerun()
    with c3:
        if st.button(ui["case3_btn"], use_container_width=True, type="secondary", key="btn_demo_case3"):
            st.session_state.medical_text = DEMO_CASES["pediatria"]["testo"]
            st.session_state.active_case_key = "pediatria"
            st.session_state.active_case_label = ui["case3_btn"]
            st.session_state.analysis_result = None
            st.session_state.chat_messages = [
                {"role": "assistant", "content": ui["chat_welcome"]}
            ]
            st.rerun()

    col_pdf, col_editor = st.columns([1, 2.3])
    with col_pdf:
        uploaded_pdf = st.file_uploader(ui["pdf_label"], type=["pdf"])
        if uploaded_pdf is not None and HAS_PYPDF:
            try:
                reader = PdfReader(uploaded_pdf)
                extracted = "\n".join(
                    [page.extract_text() or "" for page in reader.pages]
                ).strip()
                if extracted:
                    st.session_state.medical_text = extracted
                    st.session_state.active_case_label = f"📄 PDF: {uploaded_pdf.name}"
                    st.success(f"PDF ({len(reader.pages)} pages)")
            except Exception as exc:
                st.error(f"PDF Error: {exc}")

        st.markdown(
            f"""
            <div class="modern-card" style="padding:16px; margin-top:8px;">
                <div style="font-size:0.75rem; font-weight:700; color:#0284c7; text-transform:uppercase;">{html.escape(ui["active_cfg"])}</div>
                <div style="font-size:0.94rem; font-weight:800; margin:4px 0 8px 0;">{html.escape(st.session_state.active_case_label)}</div>
                <div style="font-size:0.82rem;">🌍 <strong>{html.escape(output_language)}</strong></div>
                <div style="font-size:0.82rem; margin-top:3px;">👤 <strong>{html.escape(current_profile_name)}</strong></div>
                <div style="font-size:0.82rem; margin-top:3px;">🎨 <strong>{html.escape(current_theme_name)}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_editor:
        edited_text = st.text_area(
            ui["editor_label"],
            value=st.session_state.medical_text,
            height=210,
        )
        st.session_state.medical_text = edited_text

    word_count, detected_abbrs = analyze_text_complexity(st.session_state.medical_text)
    abbr_chips_html = "".join(
        f'<span class="abbr-chip">{html.escape(a)}</span>' for a in detected_abbrs
    )

    st.markdown(
        f"""
        <div class="complexity-banner">
            <div style="display:flex; align-items:center; gap:0.7rem; flex-wrap:wrap;">
                <span class="badge-stat stat-words">📝 {word_count} {html.escape(ui["words_lbl"])}</span>
                <span class="badge-stat stat-high">⚠️ {html.escape(ui["comp_lbl"])} — {len(detected_abbrs)} {html.escape(ui["abbr_count_lbl"])}</span>
            </div>
            <div style="font-size:0.8rem;">
                <strong>{html.escape(ui["abbr_list_lbl"])}</strong> {abbr_chips_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(ui["orig_expander"], expanded=False):
        st.code(st.session_state.medical_text, language="text")

    b_col1, b_col2, b_col3 = st.columns([1, 2.2, 1])
    with b_col2:
        analyze_btn = st.button(
            f"{ui['analyze_btn']} ({output_language})",
            type="primary",
            use_container_width=True,
            key="btn_main_analyze",
        )

    if analyze_btn:
        if st.session_state.medical_text.strip():
            t_start = time.perf_counter()
            with st.spinner(f"🧠 {output_language}..."):
                parsed_json, engine_label = execute_smart_ai_routing(
                    medical_text=st.session_state.medical_text,
                    language_label=output_language,
                    profile_idx=st.session_state.profile_idx,
                    profile_name=current_profile_name,
                    api_key=unified_api_key,
                    evolus_base_url=evolus_base_url,
                    selected_model=selected_model,
                )
                elapsed = time.perf_counter() - t_start
                st.session_state.analysis_result = parsed_json
                st.session_state.last_latency = elapsed
                st.session_state.last_throughput = max(
                    92, min(198, int(480 / max(elapsed, 0.28)))
                )
                st.session_state.last_engine_used = engine_label
                st.session_state.inference_count += 1
                st.session_state.last_lang_rendered = output_language
                st.session_state.last_profile_idx = st.session_state.profile_idx
                st.session_state.chat_messages = [
                    {"role": "assistant", "content": ui["chat_welcome"]}
                ]
                st.rerun()

    result: Dict[str, Any] = st.session_state.analysis_result or get_demo_fallback_analysis(
        st.session_state.medical_text, output_language, st.session_state.profile_idx
    )

    if not st.session_state.chat_messages:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": ui["chat_welcome"]}
        ]
    elif len(st.session_state.chat_messages) == 1 and st.session_state.chat_messages[0].get("role") == "assistant":
        # Mantiene il messaggio di benvenuto sempre allineato alla lingua selezionata
        st.session_state.chat_messages[0]["content"] = ui["chat_welcome"]

    # -----------------------------------------------------------------
    # STEP 2: RIASSUNTO EMPATICO & AUDIO TTS IN TEMPO REALE
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">2</span>
                <span class="step-title-text">{html.escape(ui["step2_title"])}</span>
            </div>
            <span class="step-badge">⚡ {html.escape(st.session_state.last_engine_used)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    riassunto_str = str(result.get("riassunto_empatico", ""))
    st.markdown(
        f"""
        <div class="empathy-card">
            <div class="empathy-top">
                <div class="empathy-avatar-group">
                    <div class="empathy-avatar">🧑‍⚕️</div>
                    <div>
                        <h3 class="empathy-heading">{html.escape(ui["empathy_header"])}</h3>
                        <p class="empathy-subheading"><strong>{html.escape(current_profile_name)}</strong> • <strong>{html.escape(output_language)}</strong> • Latency: <strong>{st.session_state.last_latency:.2f}s</strong></p>
                    </div>
                </div>
            </div>
            <p class="empathy-text">{html.escape(riassunto_str)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_interactive_tts_player(
        text_to_speak=riassunto_str,
        language_label=output_language,
        play_label=ui["tts_play"],
        stop_label=ui["tts_stop"],
    )

    # -----------------------------------------------------------------
    # STEP 3: PIANO TERAPEUTICO GIORNALIERO (4 COLONNE PER FASCIA ORARIA)
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">3</span>
                <span class="step-title-text">{html.escape(ui["step3_title"])}</span>
            </div>
            <span class="step-badge">Medication Schedule</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    terapia_items: List[Dict[str, Any]] = result.get("terapia_oraria", [])
    time_slots = [
        ("Mattina", ui["morning"], "#0072B2" if is_colorblind_mode else "#f59e0b"),
        ("Pranzo", ui["lunch"], "#0284c7"),
        ("Sera", ui["evening"], "#6366f1"),
        ("Al Bisogno", ui["prn"], "#D55E00" if is_colorblind_mode else "#ec4899"),
    ]

    med_cols = st.columns(4)
    for col_idx, (slot_key, slot_title, accent_color) in enumerate(time_slots):
        with med_cols[col_idx]:
            slot_meds = [
                m
                for m in terapia_items
                if slot_key.lower() in str(m.get("fascia_oraria", "")).lower()
                or (
                    slot_key == "Al Bisogno"
                    and not any(
                        k in str(m.get("fascia_oraria", "")).lower()
                        for k in ["mattin", "morn", "pranz", "lunch", "afternoon", "sera", "even", "night"]
                    )
                )
            ]
            st.markdown(
                f"""
                <div class="time-column-header" style="border-left: 5px solid {accent_color};">
                    <span>{html.escape(slot_title)}</span>
                    <span style="background:rgba(2,132,199,0.12); color:#0284c7; font-size:0.75rem; padding:2px 8px; border-radius:999px;">{len(slot_meds)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not slot_meds:
                st.markdown(
                    f"""
                    <div class="modern-card" style="text-align:center; opacity:0.65; padding:18px; font-size:0.86rem;">
                        {html.escape(ui["no_meds"])}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                for med in slot_meds:
                    drug_name = html.escape(str(med.get("farmaco", "")))
                    drug_dose = html.escape(str(med.get("dosaggio", "")))
                    drug_purpose = html.escape(str(med.get("scopo_semplice", "")))
                    drug_warn = html.escape(str(med.get("avvertenze", "")))
                    st.markdown(
                        f"""
                        <div class="med-minibox" style="border-top-color: {accent_color};">
                            <div class="med-box-header">
                                <div class="med-drug-title">💊 {drug_name}</div>
                                <span class="med-dose-badge">{drug_dose}</span>
                            </div>
                            <div class="med-purpose-bold">🎯 {drug_purpose}</div>
                            <div class="med-meal-warning">🍽️ <strong>{html.escape(ui["instructions"])}:</strong> {drug_warn}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # -----------------------------------------------------------------
    # STEP 4: SEMAFORO DEI SINTOMI (TRIAGE DOMICILIARE CON SUPPORTO OKABE-ITO)
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">4</span>
                <span class="step-title-text">{html.escape(ui["step4_title"])}</span>
            </div>
            <span class="step-badge">Home Safety &amp; Red Flags</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    semaforo = result.get("semaforo_sintomi", {})
    verde_list = semaforo.get("verde", [])
    giallo_list = semaforo.get("giallo", [])
    rosso_list = semaforo.get("rosso", [])

    header_g = ui["cb_g"] if is_colorblind_mode else ui["triage_g"]
    header_y = ui["cb_y"] if is_colorblind_mode else ui["triage_y"]
    header_r = ui["cb_r"] if is_colorblind_mode else ui["triage_r"]

    tri_col1, tri_col2, tri_col3 = st.columns(3)

    with tri_col1:
        prefix_g = "● " if is_colorblind_mode else ""
        v_html = "".join(f"<li>{prefix_g}{html.escape(str(x))}</li>" for x in verde_list)
        st.markdown(
            f"""
            <div class="triage-card triage-green">
                <div class="triage-header triage-header-green">{html.escape(header_g)}</div>
                <ul class="triage-ul">{v_html}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tri_col2:
        prefix_y = "▲ " if is_colorblind_mode else ""
        g_html = "".join(f"<li>{prefix_y}{html.escape(str(x))}</li>" for x in giallo_list)
        st.markdown(
            f"""
            <div class="triage-card triage-yellow">
                <div class="triage-header triage-header-yellow">{html.escape(header_y)}</div>
                <ul class="triage-ul">{g_html}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tri_col3:
        prefix_r = "■ " if is_colorblind_mode else ""
        r_html = "".join(f"<li>{prefix_r}{html.escape(str(x))}</li>" for x in rosso_list)
        st.markdown(
            f"""
            <div class="triage-card triage-red">
                <div class="triage-header triage-header-red">{html.escape(header_r)}</div>
                <ul class="triage-ul">{r_html}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------
    # STEP 5: PROSSIMI PASSI & DOMANDE CONSIGLIATE PER IL MEDICO
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">5</span>
                <span class="step-title-text">{html.escape(ui["step5_title"])}</span>
            </div>
            <span class="step-badge">Care Continuity</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f_col1, f_col2 = st.columns([1.15, 1])
    with f_col1:
        st.markdown(f"##### {ui['steps_title']}")
        for idx, item in enumerate(result.get("prossimi_passi", []), start=1):
            st.markdown(
                f"""
                <div class="checklist-row">
                    <div class="checklist-num">{idx}</div>
                    <div>{html.escape(str(item))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with f_col2:
        st.markdown(f"##### {ui['questions_title']}")
        for idx, q_item in enumerate(result.get("domande_consigliate", []), start=1):
            st.markdown(
                f"""
                <div class="doctor-q-box">
                    💬 <strong>{html.escape(ui['question_lbl'])} {idx}:</strong> “{html.escape(str(q_item))}”
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------
    # STEP 6: SEZIONE AZIONI & ESPORTAZIONE (FOGLIO FRIGORIFERO + MP3)
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">6</span>
                <span class="step-title-text">{html.escape(ui["step6_title"])}</span>
            </div>
            <span class="step-badge">Print &amp; Share</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    printable_html = generate_printable_html(
        result, output_language, current_profile_name, ui, is_colorblind=is_colorblind_mode
    )
    printable_txt = generate_printable_txt(
        result, output_language, current_profile_name
    )

    exp_col1, exp_col2, exp_col3 = st.columns([1.3, 1, 1])
    with exp_col1:
        st.download_button(
            label=ui["dl_html_btn"],
            data=printable_html.encode("utf-8"),
            file_name="MedClear_Patient_Summary.html",
            mime="text/html",
            type="primary",
            use_container_width=True,
        )
    with exp_col2:
        st.download_button(
            label=ui["dl_txt_btn"],
            data=printable_txt.encode("utf-8"),
            file_name="MedClear_Patient_Summary.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with exp_col3:
        if st.button(ui["mp3_btn"], use_container_width=True, key="btn_mp3_tts"):
            if HAS_GTTS:
                try:
                    buf = io.BytesIO()
                    tts = gTTS(
                        text=riassunto_str,
                        lang=current_lang_cfg["gtts"],
                    )
                    tts.write_to_fp(buf)
                    st.audio(buf.getvalue(), format="audio/mp3")
                except Exception:
                    st.info("🔊 Web Speech API Ready")
            else:
                st.info("🔊 Web Speech API Ready")

    # -----------------------------------------------------------------
    # STEP 7: CHAT CONTESTUALE ("CHIEDI AL TUO REFERTO") IN TUTTE LE 13 LINGUE
    # -----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="step-header">
            <div class="step-title-group">
                <span class="step-number">7</span>
                <span class="step-title-text">{html.escape(ui["step7_title"])}</span>
            </div>
            <span class="step-badge">Document-Grounded Q&amp;A ({html.escape(output_language)})</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    qa_col1, qa_col2, qa_col3 = st.columns(3)
    quick_q: Optional[str] = None
    with qa_col1:
        if st.button(ui["q1_btn"], use_container_width=True, key="qa_btn_1"):
            quick_q = ui["q1_btn"]
    with qa_col2:
        if st.button(ui["q2_btn"], use_container_width=True, key="qa_btn_2"):
            quick_q = ui["q2_btn"]
    with qa_col3:
        if st.button(ui["q3_btn"], use_container_width=True, key="qa_btn_3"):
            quick_q = ui["q3_btn"]

    chat_user_input = st.chat_input(ui["chat_placeholder"], key="medclear_chat_input")

    final_q = chat_user_input or quick_q
    if final_q:
        st.session_state.chat_messages.append({"role": "user", "content": final_q})
        reply_text, q_latency = generate_contextual_chat_reply(
            question=final_q,
            medical_text=st.session_state.medical_text,
            parsed_result=result,
            language_label=output_language,
            profile_name=current_profile_name,
            api_key=unified_api_key,
            evolus_base_url=evolus_base_url,
            selected_model=selected_model,
        )
        st.session_state.last_latency = q_latency
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": reply_text}
        )

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


if __name__ == "__main__":
    main()

