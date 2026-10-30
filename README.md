# CatGenie A.I. for Home Assistant

A Home Assistant integration for the **CatGenie A.I.** self-washing litter box by PetNovations.

Sign in with your phone number and an SMS code, the same way the CatGenie app does. You don't need to capture app traffic or dig out tokens. Once connected, every CatGenie on your account shows up as a device with sensors, controls and settings.

> This is a community project. It isn't made, endorsed or supported by PetNovations, and it relies on the unofficial cloud API the mobile app uses. If PetNovations changes that API, this integration can break until it's updated.

## What you get

For each CatGenie on your account:

| Entity | Type | What it shows or does |
|---|---|---|
| SaniSolution remaining | Sensor (%) | Cartridge level. Good for "order a refill" automations. |
| Last clean | Sensor (timestamp) | When the last cycle finished. |
| Cleaning progress | Sensor (%) | Progress of the current cycle, or empty when idle. |
| Lifetime cycles | Sensor | Total cleaning cycles since activation. |
| Error | Sensor | The current error code, or `none`. |
| Cat delay | Sensor (diagnostic) | How long the unit waits after a visit before cleaning. |
| Volume | Sensor (diagnostic, off by default) | Speaker volume, 1–7. |
| Cleaning | Binary sensor | On while a cycle is running. |
| Problem | Binary sensor | On when the unit reports an error. |
| Cloud connection | Binary sensor (diagnostic) | Whether the unit is online with PetNovations' cloud. |
| Start cleaning / Stop cleaning | Buttons | Start or stop a cycle remotely. |
| Cleaning mode | Select | Automatic (after a cat visit) or Manual. |
| Child lock, Extra dry, Extra wash, Extra shake | Switches | The same settings as in the app. |

The device page also shows firmware and hardware versions. It's linked by MAC address to the same unit in your router integration, if you have one.

Data refreshes every 60 seconds, and again right after you press a button or change a setting.

## Installation

### HACS (recommended)

1. In Home Assistant, open **HACS**.
2. Open the menu (⋮) in the top right and choose **Custom repositories**.
3. Add `https://github.com/jeremy-mattern/ha-catgenie` with the type **Integration**.
4. Search for **CatGenie A.I.** in HACS and click **Download**.
5. Restart Home Assistant.

### Manual

Copy the `custom_components/catgenie` folder into your Home Assistant `config/custom_components/` folder, then restart Home Assistant.

## Setup

1. Go to **Settings → Devices & services → Add integration** and search for **CatGenie A.I.**
2. Choose **Text me a code**.
3. Enter your country code (1 for the US and Canada) and the phone number you use in the CatGenie app.
4. Enter the code from the SMS. Codes expire after a few minutes, so if one fails, go back and request a new one.

If you already have a refresh token from another tool, choose **I already have a refresh token** and paste it instead. It's checked against the cloud before it's saved.

### Signing in again

If the saved login stops working (for example, because it was revoked), Home Assistant shows a **Re-authenticate** prompt on the integration. Continue, and a new code is sent to the same number.

## Automation ideas

- Get a phone notification when **SaniSolution remaining** drops below 15%.
- Flash a light when **Problem** turns on.
- Switch **Cleaning mode** to Manual at night so the unit stays quiet, and back to Automatic in the morning.
- Pause other noisy devices while **Cleaning** is on.

## How it works

PetNovations doesn't publish an API. This integration uses the [`catgenie`](https://pypi.org/project/catgenie/) Python library, which reproduces what the official app does:

- **Login:** the app sends your phone number (encrypted) to request an SMS code, then trades the code for an access token and a long-lived refresh token. This integration stores only the refresh token, plus your phone number so re-authentication can text a new code.
- **Tokens:** access tokens last about 30 minutes and are renewed automatically from the refresh token.
- **Network quirk:** PetNovations' servers silently ignore requests that don't look like they come from a phone. They answer `200 OK` with an empty body. The library uses [`curl_cffi`](https://github.com/lexiforest/curl_cffi) to make requests that look like a mobile browser. This is why older integrations built on Home Assistant's normal HTTP client report "invalid refresh token" even when the token is fine.
- **Polling:** a single coordinator fetches every device on the account each minute. All entities read from that one response, so adding entities doesn't add cloud traffic.

### Code layout

```
custom_components/catgenie/
├── __init__.py        Sets up the entry and forwards to the platforms
├── config_flow.py     Phone + SMS sign-in, refresh-token sign-in, re-authentication
├── coordinator.py     Shared session, token handling, polling and command error handling
├── entity.py          Base entity and device-registry info
├── sensor.py          Sensors
├── binary_sensor.py   Binary sensors
├── button.py          Start and stop cleaning
├── switch.py          Child lock and cycle options
├── select.py          Cleaning mode
├── diagnostics.py     Redacted diagnostics download
└── strings.json       UI text (copied to translations/en.json)
```

## Privacy and security

- The refresh token works like a password to your CatGenie account and lasts for years. Don't share it. Home Assistant stores it in its own config storage.
- **Download diagnostics** on the integration page redacts the token, phone number, account ID, serial number and MAC address before you share it in a bug report.
- All traffic goes directly between Home Assistant and PetNovations' cloud. Nothing passes through any other server.

## Troubleshooting

- **"Could not reach the CatGenie cloud"**: PetNovations' service may be down, or Home Assistant may not have internet access. Try again in a few minutes.
- **No SMS arrives**: check that the country code and number match the ones in the CatGenie app exactly.
- **Entities are unavailable**: check that the unit is on Wi-Fi. The **Cloud connection** sensor shows whether PetNovations can see it.
- **Debug logging**: add this to `configuration.yaml` and restart, then check **Settings → System → Logs**:

  ```yaml
  logger:
    logs:
      custom_components.catgenie: debug
      catgenie: debug
  ```

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The tests use [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) and mock the cloud, so they don't need a CatGenie or an account.

## Credits

- [kclif9/catgenie-api](https://github.com/kclif9/catgenie-api): the API library this integration uses.
- [Rukongai/CatDjinni](https://github.com/Rukongai/CatDjinni): original reverse-engineering research.
- [PrimeAutomation/petnovations](https://github.com/PrimeAutomation/petnovations) and [appkins/hass-catgenie](https://github.com/appkins/hass-catgenie): earlier integrations.

## License

MIT. See [LICENSE](LICENSE).
