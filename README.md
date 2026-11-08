# PatchMon for Home Assistant

Shows which of your [PatchMon](https://patchmon.net) hosts need updates. It is read-only and cannot change or patch your hosts.

## Install

With [HACS](https://hacs.xyz):

1. Open HACS, then the three-dot menu, then **Custom repositories**.
2. Add `https://github.com/adamjeffery/patchmon-ha` with the type **Integration**.
3. Find **PatchMon** in HACS, download it, and restart Home Assistant.

Without HACS, copy `custom_components/patchmon` into your Home Assistant `config/custom_components/` folder and restart.

## Set up

1. In PatchMon, go to **Settings → Integrations → Auto-Enrollment & API** and create an **API** credential with the host `get` scope.
2. In Home Assistant, go to **Settings → Devices & services → Add integration → PatchMon** and enter your URL, token key and token secret.

| Entity | Shows |
| --- | --- |
| `sensor.patchmon_hosts_needing_updates` | Hosts with pending updates. Its `hosts` attribute feeds the host card. |
| `sensor.patchmon_outdated_packages` | Distinct outdated packages across all hosts, the same way PatchMon's dashboard counts them. |
| `sensor.patchmon_security_updates` | Distinct packages with a pending security update. |
| `sensor.<host>_updates`, `sensor.<host>_security_updates` | Counts for each host. |

## Dashboard

Add a manual card with this YAML:

```yaml
type: vertical-stack
cards:
  - type: horizontal-stack
    cards:
      - type: tile
        entity: sensor.patchmon_hosts_needing_updates
        name: Hosts
      - type: tile
        entity: sensor.patchmon_outdated_packages
        name: Outdated
      - type: tile
        entity: sensor.patchmon_security_updates
        name: Security
  - type: custom:patchmon-hosts-card
```

The host card is installed with the integration and accepts these options:

| Option | Default | Effect |
| --- | --- | --- |
| `title` | `PatchMon hosts` | Card heading. |
| `show_all` | `false` | Also lists hosts with no pending updates. |
| `entity` | `sensor.patchmon_hosts_needing_updates` | Source sensor. |

## Polling

The default interval is 5 minutes, and you can change it in **Configure**. Each poll makes one request for the host list and one for each host with pending updates. Counts only change after a host's agent reports to PatchMon.

## Development

```sh
pip install pytest-homeassistant-custom-component home-assistant-frontend
pytest
```
