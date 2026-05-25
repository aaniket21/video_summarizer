export type UiLanguage = "en" | "hi" | "ta" | "te";

type UiKey =
  | "inputTitle"
  | "inputSubtitle"
  | "videoUrl"
  | "batchHelp"
  | "noteStyle"
  | "outputLanguage"
  | "uiLanguage"
  | "uploadVideo"
  | "uploadHelp"
  | "startProcessing"
  | "processing"
  | "cancel"
  | "clear"
  | "progressTitle"
  | "progressRunning"
  | "progressCompleted"
  | "progressIdle"
  | "overall";

const MESSAGES: Record<UiLanguage, Record<UiKey, string>> = {
  en: {
    inputTitle: "Input",
    inputSubtitle: "Use either a URL or a video file. Drag-and-drop is supported.",
    videoUrl: "Video URL",
    batchHelp: "Batch supported (one URL per line)",
    noteStyle: "Note style",
    outputLanguage: "Output language",
    uiLanguage: "UI language",
    uploadVideo: "Upload video",
    uploadHelp: "Default browser FFmpeg limit is ~200MB. For larger videos, use URL + server fallback.",
    startProcessing: "Start processing",
    processing: "Processing...",
    cancel: "Cancel",
    clear: "Clear",
    progressTitle: "Progress",
    progressRunning: "Watching each pipeline step in real time.",
    progressCompleted: "Done. Outputs are ready.",
    progressIdle: "Ready when you are.",
    overall: "Overall",
  },
  hi: {
    inputTitle: "इनपुट",
    inputSubtitle: "URL या वीडियो फ़ाइल में से किसी एक का उपयोग करें। ड्रैग-एंड-ड्रॉप समर्थित है।",
    videoUrl: "वीडियो URL",
    batchHelp: "बैच समर्थित (प्रति लाइन एक URL)",
    noteStyle: "नोट शैली",
    outputLanguage: "आउटपुट भाषा",
    uiLanguage: "UI भाषा",
    uploadVideo: "वीडियो अपलोड करें",
    uploadHelp: "डिफ़ॉल्ट ब्राउज़र FFmpeg सीमा ~200MB है। बड़े वीडियो के लिए URL + सर्वर फ़ॉलबैक का उपयोग करें।",
    startProcessing: "प्रोसेसिंग शुरू करें",
    processing: "प्रोसेसिंग...",
    cancel: "रद्द करें",
    clear: "साफ़ करें",
    progressTitle: "प्रगति",
    progressRunning: "हर चरण की प्रगति वास्तविक समय में दिख रही है।",
    progressCompleted: "हो गया। आउटपुट तैयार हैं।",
    progressIdle: "जब आप तैयार हों तब शुरू करें।",
    overall: "कुल",
  },
  ta: {
    inputTitle: "உள்ளீடு",
    inputSubtitle: "URL அல்லது வீடியோ கோப்பை பயன்படுத்தவும். இழுத்து விடுதல் ஆதரிக்கப்படுகிறது.",
    videoUrl: "வீடியோ URL",
    batchHelp: "பல URL ஆதரவு (ஒரு வரிக்கு ஒன்று)",
    noteStyle: "குறிப்பு பாணி",
    outputLanguage: "வெளியீட்டு மொழி",
    uiLanguage: "UI மொழி",
    uploadVideo: "வீடியோ பதிவேற்றம்",
    uploadHelp: "உலாவி FFmpeg வரம்பு ~200MB. பெரிய வீடியோக்களுக்கு URL + சேவையக மாற்றுப்பாதை பயன்படுத்தவும்.",
    startProcessing: "செயலாக்கத்தை தொடங்கு",
    processing: "செயலாக்கம்...",
    cancel: "ரத்து செய்",
    clear: "அழி",
    progressTitle: "முன்னேற்றம்",
    progressRunning: "ஒவ்வொரு படியும் நேரடியாக கண்காணிக்கப்படுகிறது.",
    progressCompleted: "முடிந்தது. வெளியீடுகள் தயாராக உள்ளன.",
    progressIdle: "நீங்கள் தயாராக இருக்கும் போது தொடங்கலாம்.",
    overall: "மொத்தம்",
  },
  te: {
    inputTitle: "ఇన్‌పుట్",
    inputSubtitle: "URL లేదా వీడియో ఫైల్‌ను ఉపయోగించండి. డ్రాగ్-అండ్-డ్రాప్ మద్దతు ఉంది.",
    videoUrl: "వీడియో URL",
    batchHelp: "బ్యాచ్ మద్దతు (ప్రతి లైనుకు ఒక URL)",
    noteStyle: "నోట్ శైలి",
    outputLanguage: "ఆుట్‌పుట్ భాష",
    uiLanguage: "UI భాష",
    uploadVideo: "వీడియో అప్లోడ్",
    uploadHelp: "డిఫాల్ట్ బ్రౌజర్ FFmpeg పరిమితి ~200MB. పెద్ద వీడియోలకు URL + సర్వర్ ఫాల్‌బ్యాక్ వాడండి.",
    startProcessing: "ప్రాసెసింగ్ ప్రారంభించండి",
    processing: "ప్రాసెసింగ్...",
    cancel: "రద్దు",
    clear: "క్లియర్",
    progressTitle: "ప్రగతి",
    progressRunning: "ప్రతి దశను నిజ సమయంలో చూడండి.",
    progressCompleted: "పూర్తైంది. ఫలితాలు సిద్ధం.",
    progressIdle: "మీరు సిద్ధంగా ఉన్నప్పుడు ప్రారంభించండి.",
    overall: "మొత్తం",
  },
};

export function t(key: UiKey, lang: UiLanguage): string {
  return MESSAGES[lang]?.[key] || MESSAGES.en[key];
}

export const UI_LANGUAGE_OPTIONS: { value: UiLanguage; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
];
