/** Erklärtexte für MITRE ATT&CK Taktiken (Kill Chain) */
const TACTIC_MAP: Record<string, string> = {
  reconnaissance: 'Aufklärung: Sammeln von Informationen über das Ziel (z.B. E-Mail-Adressen, Systeme).',
  'resource-development': 'Ressourcen-Entwicklung: Aufbau von Infrastruktur (Domains, Konten) für den Angriff.',
  'initial-access': 'Initialer Zugang: Erstes Eindringen ins Netzwerk (z.B. Phishing, Exploit).',
  execution: 'Ausführung: Starten von schädlichem Code auf dem Zielsystem.',
  persistence: 'Persistenz: Sicherstellen, dass der Zugang auch nach Neustart erhalten bleibt.',
  'privilege-escalation': 'Rechteerweiterung: Erlangen höherer Berechtigungen (z.B. Admin).',
  'defense-evasion': 'Abwehr-Umgehung: Vermeiden von Erkennung (z.B. Antivirus deaktivieren).',
  'credential-access': 'Zugriff auf Anmeldedaten: Auslesen von Passwörtern und Tokens.',
  discovery: 'Erkundung: Erkunden des Netzwerks (Systeme, Benutzer, Daten).',
  'lateral-movement': 'Laterale Bewegung: Ausbreitung zu weiteren Systemen im Netzwerk.',
  collection: 'Sammlung: Sammeln der zu exfiltrierenden Daten.',
  'command-and-control': 'Befehl & Kontrolle: Kommunikation mit dem Angreifer-Server (C2).',
  exfiltration: 'Exfiltration: Herausschleusen der gestohlenen Daten.',
  impact: 'Auswirkung: Störung oder Zerstörung (z.B. Ransomware, Datenlöschung).',
};

/** Normalisiert Taktik-ID für Lookup (z.B. "Initial Access" → "initial-access") */
function normalizeTacticId(id: string): string {
  return id.toLowerCase().replace(/\s+/g, '-').trim();
}

export function getTacticExplanation(tacticId: string | undefined): string {
  if (!tacticId) return '';
  return TACTIC_MAP[tacticId] || TACTIC_MAP[normalizeTacticId(tacticId)] || '';
}

export const TACTIC_EXPLANATIONS = TACTIC_MAP;

/** Erklärtexte für Ablauf-Schritte */
export const STEP_EXPLANATIONS: Record<string, string> = {
  generator: 'Der Generator (LLM) erzeugt den nächsten MSEL-Schritt basierend auf Bedrohungskontext und bisherigem Verlauf.',
  validator: 'Der Validator prüft den Schritt gegen den MITRE ATT&CK Reasoning Graph (Neo4j): Technik existiert, Pfad ist kausal gültig, DORA-Constraints erfüllt.',
  auditor: 'Der Auditor bewertet die Qualität des Szenarios.',
  retry: 'Neuer Versuch nach abgelehntem Schritt.',
};
