# Mantle für Home Assistant

Verbindet Home Assistant mit einem [Mantle](https://github.com/BjoernSchotte) Hub, dem Launcher für
Android-TV-Geräte.

- **Geräte:** Jeder Fernseher des Hubs wird ein Gerät mit „Online“, „Bildschirm“, „App im Vordergrund“,
  „Mantle-Version“, „Konfiguration“ und dem Knopf „Neu laden“. Änderungen kommen live (WebSocket).
- **Dienste:**
  - `mantle.open_space` öffnet einen Space auf einem Fernseher, z. B. aus einer Automation.
  - `mantle.call_action` ruft eine beliebige Hub-Aktion auf und gibt ihr Ergebnis zurück.
- **Events:** Hub-Events kommen als `mantle_event` (`type`, `data`, `origin`). Dafür braucht es das Token
  eines Admin-Kontos.

## Einrichten

1. In HACS unter „Benutzerdefinierte Repositories“ dieses Repo als „Integration“ hinzufügen, „Mantle“
   installieren, Home Assistant neu starten.
2. Im Hub ein Konto für Home Assistant anlegen und dort unter Profil → Zugangstoken ein Token erzeugen.
3. In Home Assistant: Einstellungen → Geräte & Dienste → „Mantle“. Der Hub wird per mDNS gefunden; sonst
   die Adresse eingeben.

## Beispiel

```yaml
automation:
  - alias: Abends Homelab auf dem Beamer
    triggers:
      - trigger: time
        at: "19:00:00"
    actions:
      - action: mantle.open_space
        data:
          device_id: <Gerät „Beamer Schlafzimmer“>
          space: homelab
```

Die Quelle liegt im Mantle-Repo unter `integrations/homeassistant/`; dieses Repo ist ihr Spiegel für HACS.
