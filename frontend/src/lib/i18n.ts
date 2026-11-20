import { useAuth } from "./auth";

const en = {
  space: "My skill-building space",
  checkin: "Daily check-in", checkinHint: "How are you feeling today, and how did you sleep?",
  journal: "Journal", journalHint: "Private notes. Only you can see them unless you choose to share one.",
  journeys: "Journeys", journeysHint: "Step-by-step programmes from your therapist.",
  insights: "Insights", insightsHint: "Your mood, sleep and exercises over the last 30 days.",
  reminders: "Reminders", remindersHint: "Gentle nudges by email. Off unless you turn them on.",
  open: "Open", back: "Back to my space",
  mood: "Mood", moodScale: "1 is low, 5 is good", sleepHours: "Hours slept", note: "Note (optional)",
  save: "Save", saving: "Saving…", saved: "Saved. Thank you for checking in.", updateToday: "Update today's check-in",
  alreadyToday: "You checked in today. You can change it below.",
  writeEntry: "Write an entry", shareWithTherapist: "Share this entry with my therapist",
  shared: "Shared with therapist", private: "Private", share: "Share", unshare: "Make private",
  noEntries: "No entries yet.", saveEntry: "Save entry",
  week: "Week", thisWeek: "This week", steps: "steps", done: "Done", markDone: "Mark as done",
  progress: "Progress", noJourneys: "No programme yet. Your therapist can assign one.", exercise: "Exercise",
  moodChart: "Mood (1-5)", sleepChart: "Sleep (hours)", exerciseChart: "Exercises completed",
  checkins: "Check-ins", avgMood: "Average mood", avgSleep: "Average sleep (h)", exercisesDone: "Exercises completed",
  exercisesAssigned: "Exercises assigned", noData: "No check-ins yet. Your charts will appear here.", date: "Date",
  remDaily: "Daily check-in reminder", remNudge: "Reminders about exercises from my therapist",
  remOff: "Off", remOn: "On", remNote: "Sent by email at most once a day. You can switch these off at any time.",
  launchTitle: "Launch with Saarthi", launchIntro: "Describe your practice idea. The assistant proposes a page address on Saarthi, page text, a welcome email and a checklist, plus optional ideas for your own domain. It only proposes: nothing is bought, changed or published until you approve.",
  launchIdea: "Your practice idea", launchStart: "Draft my launch plan", launchWorking: "Working…", launchSteps: "Agent steps",
  launchDomains: "Domain options", launchAvailable: "Available", launchTaken: "Taken", launchUnknown: "Availability unknown", launchNotChecked: "Not checked",
  launchUseDomain: "Use this domain", launchConfirmed: "Confirmed domain", launchDns: "DNS plan", launchDnsHint: "Point the domain at the Saarthi server. Booking stays inside Saarthi.",
  launchDnsManual: "Add these records at your domain registrar. Automatic changes are turned off on this server.", launchDnsApply: "Apply DNS records", launchDnsDone: "DNS records applied.",
  launchPage: "Draft page", launchEmail: "Welcome email", launchChecklist: "Launch checklist", launchApprove: "Approve", launchEdit: "Edit", launchReject: "Reject",
  launchSaveEdit: "Save changes", launchCancel: "Cancel", launchTokens: "Tokens used", launchCost: "Estimated cost", launchApproved: "Approved. The page text is saved as your page draft; publishing and domain steps stay separate.",
  launchRejected: "Rejected. Nothing was changed.", launchManual: "Set up manually", launchTagline: "Tagline", launchAbout: "About", launchSubject: "Subject", launchBody: "Body", launchOnePerLine: "One step per line",
  launchSlug: "Your page address", launchSlugHint: "Your page and its Book flow are always served by Saarthi at this address.", launchUseSlug: "Use this address", launchChosen: "Chosen",
  launchOptional: "Use your own domain (optional)", launchOptionalHint: "Optional. A custom domain only points at the same Saarthi page; booking stays inside Saarthi.",
  launchCheckGoDaddy: "Check and register on GoDaddy", launchNotCheckedInApp: "Not checked in-app", launchPurchaseNote: "You complete the purchase on GoDaddy. Saarthi never buys a domain for you.",
  launchRegistered: "I have registered this domain", launchCopy: "Copy", launchCopied: "Copied", launchRecordsHint: "Add these records at your registrar, then allow some time for them to take effect.",
} as const;
export type Key = keyof typeof en;

const hi: Record<Key, string> = {
  space: "मेरा कौशल-निर्माण स्पेस",
  checkin: "दैनिक चेक-इन", checkinHint: "आज आप कैसा महसूस कर रहे हैं, और नींद कैसी रही?",
  journal: "जर्नल", journalHint: "निजी नोट्स। जब तक आप साझा करना न चुनें, केवल आप इन्हें देख सकते हैं।",
  journeys: "यात्राएँ", journeysHint: "आपके थेरेपिस्ट के चरण-दर-चरण कार्यक्रम।",
  insights: "अंतर्दृष्टि", insightsHint: "पिछले 30 दिनों में आपका मूड, नींद और अभ्यास।",
  reminders: "रिमाइंडर", remindersHint: "ईमेल से हल्के अनुस्मारक। जब तक आप चालू न करें, बंद रहते हैं।",
  open: "खोलें", back: "मेरे स्पेस पर वापस",
  mood: "मूड", moodScale: "1 कम है, 5 अच्छा है", sleepHours: "सोने के घंटे", note: "नोट (वैकल्पिक)",
  save: "सहेजें", saving: "सहेजा जा रहा है…", saved: "सहेज लिया गया। चेक-इन करने के लिए धन्यवाद।", updateToday: "आज का चेक-इन बदलें",
  alreadyToday: "आपने आज चेक-इन कर लिया है। आप इसे नीचे बदल सकते हैं।",
  writeEntry: "प्रविष्टि लिखें", shareWithTherapist: "यह प्रविष्टि मेरे थेरेपिस्ट के साथ साझा करें",
  shared: "थेरेपिस्ट के साथ साझा", private: "निजी", share: "साझा करें", unshare: "निजी करें",
  noEntries: "अभी कोई प्रविष्टि नहीं।", saveEntry: "प्रविष्टि सहेजें",
  week: "सप्ताह", thisWeek: "इस सप्ताह", steps: "चरण", done: "पूरा", markDone: "पूरा हुआ चिह्नित करें",
  progress: "प्रगति", noJourneys: "अभी कोई कार्यक्रम नहीं। आपके थेरेपिस्ट एक दे सकते हैं।", exercise: "अभ्यास",
  moodChart: "मूड (1-5)", sleepChart: "नींद (घंटे)", exerciseChart: "पूरे किए गए अभ्यास",
  checkins: "चेक-इन", avgMood: "औसत मूड", avgSleep: "औसत नींद (घंटे)", exercisesDone: "पूरे किए गए अभ्यास",
  exercisesAssigned: "दिए गए अभ्यास", noData: "अभी कोई चेक-इन नहीं। आपके चार्ट यहाँ दिखेंगे।", date: "तारीख",
  remDaily: "दैनिक चेक-इन रिमाइंडर", remNudge: "थेरेपिस्ट के दिए अभ्यासों के रिमाइंडर",
  remOff: "बंद", remOn: "चालू", remNote: "ईमेल से दिन में अधिकतम एक बार। आप इन्हें कभी भी बंद कर सकते हैं।",
  launchTitle: "सारथी के साथ लॉन्च करें", launchIntro: "अपने प्रैक्टिस का विचार लिखें। सहायक सारथी पर पेज का पता, पेज टेक्स्ट, स्वागत ईमेल और चेकलिस्ट सुझाता है, साथ में अपने डोमेन के वैकल्पिक विचार। यह केवल सुझाव देता है: आपकी मंज़ूरी के बिना कुछ भी खरीदा, बदला या प्रकाशित नहीं होता।",
  launchIdea: "आपके प्रैक्टिस का विचार", launchStart: "मेरी लॉन्च योजना बनाएँ", launchWorking: "काम चल रहा है…", launchSteps: "एजेंट के चरण",
  launchDomains: "डोमेन विकल्प", launchAvailable: "उपलब्ध", launchTaken: "लिया जा चुका", launchUnknown: "उपलब्धता अज्ञात", launchNotChecked: "जाँचा नहीं गया",
  launchUseDomain: "यह डोमेन चुनें", launchConfirmed: "पुष्ट डोमेन", launchDns: "DNS योजना", launchDnsHint: "डोमेन को सारथी सर्वर की ओर इंगित करें। बुकिंग सारथी के भीतर ही रहती है।",
  launchDnsManual: "ये रिकॉर्ड अपने डोमेन रजिस्ट्रार पर जोड़ें। इस सर्वर पर स्वचालित बदलाव बंद हैं।", launchDnsApply: "DNS रिकॉर्ड लागू करें", launchDnsDone: "DNS रिकॉर्ड लागू हो गए।",
  launchPage: "पेज का मसौदा", launchEmail: "स्वागत ईमेल", launchChecklist: "लॉन्च चेकलिस्ट", launchApprove: "मंज़ूर करें", launchEdit: "संपादित करें", launchReject: "अस्वीकार करें",
  launchSaveEdit: "बदलाव सहेजें", launchCancel: "रद्द करें", launchTokens: "उपयोग किए गए टोकन", launchCost: "अनुमानित लागत", launchApproved: "मंज़ूर। पेज टेक्स्ट आपके पेज मसौदे के रूप में सहेजा गया; प्रकाशन और डोमेन के चरण अलग रहते हैं।",
  launchRejected: "अस्वीकृत। कुछ भी नहीं बदला।", launchManual: "हाथ से सेट अप करें", launchTagline: "टैगलाइन", launchAbout: "परिचय", launchSubject: "विषय", launchBody: "संदेश", launchOnePerLine: "हर पंक्ति में एक चरण",
  launchSlug: "आपके पेज का पता", launchSlugHint: "आपका पेज और उसका बुकिंग प्रवाह हमेशा इसी पते पर सारथी से चलता है।", launchUseSlug: "यह पता चुनें", launchChosen: "चुना गया",
  launchOptional: "अपना डोमेन इस्तेमाल करें (वैकल्पिक)", launchOptionalHint: "वैकल्पिक। कस्टम डोमेन केवल उसी सारथी पेज की ओर इंगित करता है; बुकिंग सारथी के भीतर ही रहती है।",
  launchCheckGoDaddy: "GoDaddy पर जाँचें और पंजीकृत करें", launchNotCheckedInApp: "ऐप में जाँचा नहीं गया", launchPurchaseNote: "खरीदारी आप GoDaddy पर पूरी करते हैं। सारथी आपके लिए कभी डोमेन नहीं खरीदता।",
  launchRegistered: "मैंने यह डोमेन पंजीकृत कर लिया है", launchCopy: "कॉपी करें", launchCopied: "कॉपी हो गया", launchRecordsHint: "ये रिकॉर्ड अपने रजिस्ट्रार पर जोड़ें, फिर लागू होने में कुछ समय दें।",
};

export const STRINGS = { en, hi };

export function useLang(): "en" | "hi" {
  const { user } = useAuth();
  return user?.language === "hi" ? "hi" : "en";
}

export function useT() {
  const lang = useLang();
  return (k: Key): string => STRINGS[lang][k];
}
