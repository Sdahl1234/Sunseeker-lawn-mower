# Sunseeker lawn mower integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

Home assistant integration from lawnmower using the robotic-mower connect APP (Old models) or Sunseeker Robot App (new wireless models).

#### V1.2.16

## Tested models
  - Adano RM5, RM6, RM9
  - Brücke RM501
  - Sunseeker X3, X4, X5, X7
  - Sunseeker X3, X5, X7 Gen2
  - Sunseeker V1, V18, V3

## Install
#### HACS (recommended)
In HACS, search for **Sunseeker robotic mower** and click **Download**.
Restart Home Assistant and go to *Devices and Services* and press *+Add integration*.
Search for *Sunseeker robotic mower* and add it.
#### HACS Custom Repository
In HACS, add a custom repository and use https://github.com/Sdahl1234/Sunseeker-lawn-mower
Download from HACS.
Restart Home Assistant and go to *Devices and Services* and press *+Add integration*.
Search for *Sunseeker robotic mower* and add it.
#### Manually
In Home Assistant, create a folder under *custom_components* named *sunseeker* and copy all the content of this project to that folder.
Restart Home Assistant and go to *Devices and Services* and press *+Add integration*.
Search for *Sunseeker robotic mower* and add it.

## Python version
This integration requires **Python 3.14 or newer**. Home Assistant 2025.1 and later ships with Python 3.14, so no manual action is needed when running a supported HA release.

## Configuration
- Producent: If your mower is not on the list, just select sunseeker
- Model_id: New if your mower is wireless
- Region: EU or US. Only used in wireless mowers
- Name: Any name you want to call your account.
- Email and Password: Your loging credentials to the app.
<img width="340" height="579" alt="image" src="https://github.com/user-attachments/assets/ce71f60a-338c-41f6-b3ff-6789bcb44810" />


## Translation
English, Danish, German, Finnish, French and Polish

# Lovelace cards (Only working with wireless models)
- Schedule card: https://github.com/Sdahl1234/sunseeker-schedule-card
- Mower control card: https://github.com/Sdahl1234/sunseeker-mower-control-card
- Mower zones card: https://github.com/Sdahl1234/sunseeker-zone-card
- Mower map-edit card: https://github.com/Sdahl1234/sunseeker-map-edit-card
- Mower work-record card: https://github.com/Sdahl1234/sunseeker-work-record-card

# Entities

## All wireless models (V1, V18, V3, X, S)

The following entities are available on all wireless models:

### Lawn mower
All states and actions (Start, Pause, Stop, Home)
#### States
- Going home, Charging, Standby, Working, Pause, Error, Returning, Returning paused, Charged, Offline, Locating, Stopped, Continue mowing, Stuck, Updating firmware
#### Actions
- **Start**, **Pause**, **Stop**, **Home**

### Binary sensors
- **Online** - Connected or Disconnected
- **Rain sensor active** - on/off

### Sensors
- **Mower status** - Current mower state
- **Battery** - Battery percentage
- **Robot signal** - Signal strength to mower
- **State change error** - Error from last setting change
- **Rain sensor status** - Dry, Dry countdown, Wet
- **Rain sensor delay** - Configured delay in minutes
- **Rain sensor countdown** - Time left before resuming mowing
- **Error code** - Current error code
- **Error** - Error text
- **Event** - Event codes mapped to text
- **Wifi level** - Wifi signal strength
- **Schedule** - Schedule sensor with schedule attributes
- **Mower firmware** - Installed firmware version
- **Mower new firmware** - Latest available firmware version

### Numbers
- **Rain delay** - Minutes from rain sensor dry to resume mowing

### Switches
- **Rain sensor** - Enable/disable the rain sensor

### Buttons
- **Start** - Start the mower
- **Home** - Send the mower home
- **Pause** - Pause the mower

### Device tracker
- **Mower location** - Anti-theft GPS location

### Update
- **Mower firmware** - Firmware update notification

---

## V models (V18, V3)

In addition to the shared entities above, V8 and V3 models include:

### Buttons
- **Border** - Cut border
- **Stop** - Stop the mower

### Switches
- **Ride on edge** - Mow on top of the edge when cutting border

### Select
- **Border distance** - Far, Moderate, Close

### Sensors
- **Blade speed** - Current blade speed
- **Blade height** - Current blade height

### Sensors (V3)
- **Actual mowing time** - Time mowed since last charge

---

## V1

In addition to the shared entities above, V1 includes:

### Buttons
- **Border** - Cut border
- **Stop** - Stop the mower

### Switches
- **Pause schedule** - Pause/resume the mowing schedule

### Select
- **Border distance** - Close, Far
- **Docking mode** - Smart, Traceless
- **Ride on edge** - Off, On
- **Automatic screen timeout** - Off, 30, 60, 90 seconds

---

## X models (X3, X4, X5, X7, X9) and S models (S3, S4, S5)

In addition to the shared entities above, X and S models include:

**Generation overview:**
- **Gen1:** X3, X4, X5, X7, X9 / S3, S4, S5
- **Gen2:** X3 Gen2, X5 Gen2, X7 Gen2 / S5 Gen2
- **Gen3:** X5 Gen3, X7 Gen3, X7 Plus Gen3

### Buttons
- **Stop** - Stop the mower *(all X and S)*
- **End task** - End the current task *(all X and S)*
- **Reset blade** - Reset blade health to 100% *(all X and S)*
- **Reset bladeplade** - Reset bladeplade health to 100% *(all X and S)*
- **Reset small blade** - Reset small blade *(Gen2 and Gen3 only)*
- **Reset small bladeplade** - Reset small bladeplade health *(Gen2 and Gen3 only)*

### Switches
- **Custom zones** - Enable user-defined zone settings *(all X and S)*
- **Cut edge first** - Mow the edge before the main area *(all X and S)*
- **Repeat time work** - Continue mowing after the end of a cycle *(all X and S)*
- **Pause schedule** - Pause/resume the mowing schedule *(all X and S)*
- **Night work** - Enable/disable night work *(X4, X5, X7, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S4, S5, S5 Gen2)*
- **Energy saving** - Turn on/off light *(X4, X5, X7, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S5)*
- **{zone} Zigzag active 1–4** - Enable/disable each zigzag angle slot per zone *(Gen2 and Gen3 only)*
- **Auto ride edge** - Automatically map and mow outside borders *(X4, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S4)*
- **Cliff detect** - Enable/disable cliff detect *(X3 Gen2, X4, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S4)*

### Select
- **Zones** - Dropdown of all map zones *(all X and S)*
- **Work speed** - Slow, Normal, Fast *(all X and S)*
- **Cutting gap** - Narrow, Normal, Wide *(all X and S)*
- **Edge trim frequency** - Every time, Every 2nd time, Every 3rd time *(all X and S)*
- **Cutting pattern** - Standard, Change pattern, User defined, Effective, Multi angle *(all X and S)*
- **{zone} Cutting pattern** - Per-zone cutting pattern *(all X and S)*
- **{zone} Work speed** - Per-zone work speed *(all X and S)*
- **{zone} Cutting gap** - Per-zone cutting gap *(all X and S)*
- **Map drawing** - Simple, Simple with border, Advanced, Advanced with border, All *(all X and S)*
- **Avoiding objects** - No touch, Slow touch *(X3, X3 Gen2, X4, X5, X7, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S4, S5)*
- **AI Sensitivity** - Low, High *(X3, X5, X7, S5)*
- **Docking mode** - Smart, Along the edge, Direct *(X3, X3 Gen2, X4, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S4)*
- **Border distance** - Distance to keep from the border *(X3 Gen2, X4, X9, X5 Gen2, X5 Gen3, X7 Gen2, X7 Gen3, S4)*

### Numbers
- **Blade speed** - Speed of the cutting blades *(all X and S)*
- **Blade height** - Height of the cutting blades *(all X and S)*
- **{zone} Blade speed** - Blade speed per zone *(all X and S)*
- **{zone} Blade height** - Blade height per zone *(all X and S)*
- **Cutting angle** - Global cutting angle *(Gen1 only)*
- **{zone} Cutting angle** - Per-zone cutting angle *(Gen1 only)*
- **Zigzag angle 1–4** - Global zigzag pass angles (0–180°) *(Gen2 and Gen3 only)*
- **{zone} Zigzag angle 1–4** - Per-zone zigzag pass angles (0–180°) *(Gen2 and Gen3 only)*

### Sensors
- **4G Net strength** - 4G network signal strength (if SIM module installed) *(all X and S)*
- **Blade speed** - Current blade speed *(all X and S)*
- **Blade height** - Current blade height *(all X and S)*
- **Covered area** - Area covered in the current mowing cycle *(all X and S)*
- **Total area** - Total map area *(all X and S)*
- **Progress** - Progress of the current mowing cycle *(all X and S)*
- **Blade health** - Blade health percentage *(all X and S)*
- **Blade time left** - Time remaining before blade replacement *(all X and S)*
- **Cutterplade health** - Cutterplade health percentage *(all X and S)*
- **Cutterplade time left** - Time remaining before cutterplade cleaning *(all X and S)*
- **Actual mowing time** - Time mowed since last charge *(all X and S)*
- **Work records** - Work record data (used with the work record card) *(all X and S)*
- **Work region** - Zone the mower is currently in, based on its live map position *(all X and S)*
- **{zone} Estimated time** - Estimated mowing time per zone *(all X and S)*
- **{zone} Area** - Area size per zone *(all X and S)*
- **Small blade health** - Small blade health percentage *(Gen2 and Gen3 only)*
- **Small blade time left** - Time remaining before small blade replacement *(Gen2 and Gen3 only)*
- **Small cutterplade health** - Small cutterplade health percentage *(Gen2 and Gen3 only)*
- **Small cutterplade time left** - Time remaining before small cutterplade cleaning *(Gen2 and Gen3 only)*
- **Base firmware** - Installed base station firmware version *(Gen1 only)*
- **Base new firmware** - Latest available base station firmware version *(Gen1 only)*
- **Base serialnumber** - Base station serial number *(Gen1 only)*

### Camera
- **Live map** - Live map with mower movement *(all X and S)*

### Images
- **Map** - Map image (use with the map-edit card) *(all X and S)*
- **Heat map** - Heat map image *(all X and S)*
- **Wifi map** - Wifi signal map image *(all X and S)*
- **4G net map** - 4G net map *(Gen2 and Gen3 only)*

### Text
- **Charger GPS position** - Set the GPS coordinates of the charging station for accurate mower position tracking *(all X and S)*

### Device tracker
- **Mower location** - Anti-theft GPS location *(all wireless models)*
- **Mower position** - Calculated GPS position derived from map coordinates *(all X and S)*

---

## Rain sensor and controls
- **Switches**
  - **Rain sensor** - Turn on/off the rain sensor
- **Numbers**
  - **Rain delay** - Minutes from when the rain sensor is dry to start mowing again
- **Binary sensors**
  - **Rain sensor active** - on/off
- **Sensors**
  - **Rain sensor status** - Dry, Dry countdown, Wet
  - **Rain sensor delay** - Same as the number entity
  - **Rain sensor countdown** - The time left before starting mowing again

## Zones *(X and S models)* - for each zone on your map you will have the following entities
- **Sensors**
  - **{zonename} Estimated time** - Estimated time to mow the area
  - **{zonename} Area** - Area size
- **Settings**
  - **{zonename} Cutting gap** - Narrow, Normal, Wide
  - **{zonename} Cutting pattern** - Standard, Change pattern, User defined
  - **{zonename} Work speed** - Slow, Normal, Fast
  - **{zonename} Cutting angle** *(Gen1 only)* - Cutting angle when pattern is User defined
  - **{zonename} Blade speed** - Speed of the blades
  - **{zonename} Blade height** - Height of the blades
- **Zone settings (Gen2 and Gen3 only)**
  - **{zonename} Cutting pattern** also supports **Effective** and **Zigzag**
  - **{zonename} Zigzag angle 1–4** *(Number)* - The angle for each zigzag pass in this zone (0–180°). Only active when zone Cutting pattern is Zigzag.
  - **{zonename} Zigzag active 1–4** *(Switch)* - Enable/disable each zigzag angle slot for this zone.
- Easy way to control the zones is using the zone card https://github.com/Sdahl1234/sunseeker-zone-card
<img width="1004" height="853" alt="image" src="https://github.com/user-attachments/assets/e5e50298-bd6f-44fe-b570-79ac30f8e55d" />

## Schedule
- **Pause schedule** *(V1, X, S)* - Turns on/off the schedule
- **Repeat time work** *(V, X, S)* - If enabled the mower continues mowing after end cycle
- **Schedule** - Sensor with attributes containing the schedule. This is the one you must use in the schedule card https://github.com/Sdahl1234/sunseeker-schedule-card
<img width="905" height="854" alt="image" src="https://github.com/user-attachments/assets/f8674bcc-1afd-4ef4-9890-8c9e57b1ca72" />

## Map *(X and S models only)*
- **Map** - Image of the map - Use this one in the sunseeker-map-edit-card
- **Live map** - Camera entity of Live Map with mower movements
- **Heat map** - Image of the heat map
- **Wifi map** - Image of the wifi map
- **4G map** - Image of the 4G map *(Gen2 and Gen3 only)*

## Mower Map edit card
https://github.com/Sdahl1234/sunseeker-map-edit-card
<img width="1612" height="539" alt="image" src="https://github.com/user-attachments/assets/c7018b9c-1d94-495f-b47d-ab00c1029020" />

## Mower control card
https://github.com/Sdahl1234/sunseeker-mower-control-card
<img width="901" height="714" alt="image" src="https://github.com/user-attachments/assets/78235dbd-8555-4bed-b386-7da1a846735f" />

## Mower work record card *(X and S models only)*
- **Sensors**
  - **Work Records** - Sensor with the work records data

https://github.com/Sdahl1234/sunseeker-work-record-card
<img width="1614" height="502" alt="image" src="https://github.com/user-attachments/assets/30d2017a-7a19-414a-9e94-ec3026c94827" />

## Device tracker
- **Mower location** - Anti-theft location. Returns the latitude and longitude coordinates of the device. *(all models)*
- **Mower position** - Calculated GPS position of the mower, derived from its map coordinates. *(X and S models only)*

## Charger GPS position *(X and S models only)*
For the **Mower position** tracker to be accurate, the integration needs to know the real-world GPS location of the charging station. The device's built-in GPS (`Mower location`) is not always reliable, so you can provide the charger coordinates manually.

- **Charger GPS position** (text entity) - Paste the charger's GPS coordinates in Google Maps format: `57.33458060994386, 10.518281265571325`
  - Right-click the charger location in Google Maps and copy the coordinates
  - Paste the value into this text entity
  - The coordinates are saved to `ChargerGPS-{serial}.json` in your config directory and restored on restart
  - Once set, **Mower position** will use the charger's known GPS as the anchor point instead of the device's internal RTK base coordinates

## Device update
- **Notification** - Notification when mower or basestation has firmware updates**

## Actions

| Action | Description | Fields |
|---|---|---|
| **Start mowing** | Start the mower, optionally limited to specific zones | `entity_id` (lawn_mower), `zones` – list of zone names |
| **Stop mowing** | Stop the mower | `entity_id` (lawn_mower) |
| **Start mowing selected area** | Start mowing a manually drawn polygon area | `entity_id` (lawn_mower), `points` – list of `[x, y]` coordinates |
| **Stop task** | Stop the current mower task | `entity_id` (lawn_mower) |
| **Set schedule** | Apply a complete schedule object to the mower | `entity_id` (schedule sensor), `schedule` – schedule dict |
| **Set map** | Upload updated map data to the mower | `entity_id` (image entity), `schedule` – map dict |
| **Backup map** | Save the current map under a backup ID | `entity_id` (lawn_mower), `mapid` – backup ID string |
| **Restore map** | Restore a previously backed-up map | `entity_id` (lawn_mower), `mapid` – backup ID string |
| **Delete backup** | Delete a backed-up map | `entity_id` (lawn_mower), `mapid` – backup ID string |
| **Change pin** | Change the mower's 4-digit PIN code | `entity_id` (lawn_mower), `old_pin`, `new_pin` |
| **Load work record** | Load the detail of a single work record by URL | `entity_id` (lawn_mower), `url` – work record URL |
| **Get work records** | Retrieve a page of work records | `entity_id` (lawn_mower), `pos` (default 1), `count` (default 10, max 50), `append` (default false) |

#
**This section is for the old wired models.**
**I'm not going to add new features, but i will do my best to keep it working**
****
# Entities old models
## Lawn mower
#### states
- Standby
- Mowing
- Going home
- Charging
- Border
- Error
#### Actions
- **Start** - Starts the mower
- **Pause** - Pause the mower
- **Home**  - Sending the mower home

## Buttons
- **Start** - Starts the mower
- **Home** - Sending the mower home
- **Pause** - Pause the mower
- **Border** - If the mower is in the dock it will mowe the border

## Switches
- **Rain sensor** - Turn on/off the rain sensor
- **Multizone** - Turn on/off using zones
- **Multizone auto** - Turn on/off auto multizone

## Numbers
- **Rain delay** - Minutes from when the rain sensor is dry to start mowing again
- **Zone 1** - percentage of the start of zone 1
- **Zone 2** - percentage of the start of zone 2
- **Zone 3** - percentage of the start of zone 3
- **Zone 4** - percentage of the start of zone 4

## Text
*Format of the text fields: Start and end time format HH:MM. Add Trim to mowe the border. ex. "06:15 - 17:00 Trim", "06:15 - 17:00", "08:00 - 24:00" or whole day "00:00 - 24:00"*

- **Schedule Monday** - Text field to update the moday schedule.
- **Schedule Tuesday** - Text field to update the moday schedule.
- **Schedule Wednesday** - Text field to update the moday schedule.
- **Schedule Thursday** - Text field to update the moday schedule.
- **Schedule Friday** - Text field to update the moday schedule.
- **Schedule Saturday** - Text field to update the moday schedule.
- **Schedule Sunday** - Text field to update the moday schedule.

## Binary sensors
- **Dock** - states: home or away
- **Rain sensor active** - on/off
- **Multizone** - on/off
- **Multizone auto** - on/off
- **Online** - Connected (the robot is turn on an conneced to wifi) / Disconnected

## Sensors
- **Battery** - Percentage of the battery
- **Mower** state - Same state af the mower entity
- **Wifi level** - 0, 1, 2 or 3
- **State change error** - Return the error message if any, whene changing the settings. ex. "The mower is offline"
- **Rain sensor status** - Dry, Dry countdown, Wet
- **Rain sensor delay** - Same as the number entity
- **Rain sensor countdown** - The time left before starting mowing again
- **Actual mowingtime** - The time the mower has been mowing since last charge
- **Zone1,2,3,4** - Same as the number entity
- **Error** - error text returned for the mower
- **Errorcode** - The errorcode returned for the mower
- **Schedule** - The state is always schedule, and contains the schedule settings as attributes.
- **Event** - Eventscodes maped to text from app

## Device tracker
- **Robot location** - Some kind of anti theft thing. Returns the latitude and longitude coordinates of the device.
