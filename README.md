# Sunseeker lawn mower integration for Home Assistant
Home assistant integration from lawnmower using the robotic-mower connect APP (Old models) or Sunseeker Robot App (new wireless models).

#### V1.2.1

## Tested models
  - Adano RM6
  - Brücke RM501
  - Sunseeker X3, X5, X7
  - Sunseeker V1, V3

## Install
#### Manually
In Home Assistant, create a folder under *custom_components* named *sunseeker* and copy all the content of this project to that folder.
Restart Home Assistant and go to *Devices and Services* and press *+Add integration*.
Search for *Sunseeker robotic mower* and add it.
#### HACS Custom Repository
In HACS, add a custom repository and use https://github.com/Sdahl1234/Sunseeker-lawn-mower
Download from HACS.
Restart Home Assistant and go to *Devices and Services* and press *+Add integration*.
Search for *Sunseeker robotic mower* and add it.

## Configuration
- Producent: If your mower is not on the list, just select sunseeker
- Model_id: New if your mower is wireless
- Region: EU or US. Only used in wireless mowers
- Name: Any name you want to call your account.
- Email and Password: Your loging credentials to the app.
<img width="340" height="579" alt="image" src="https://github.com/user-attachments/assets/ce71f60a-338c-41f6-b3ff-6789bcb44810" />


## Translation
English, Danish, German, Finnish and French

# Lovelace cards (Only working with wireless models)
- Schedule card: https://github.com/Sdahl1234/sunseeker-schedule-card
- Mower control card: https://github.com/Sdahl1234/sunseeker-mower-control-card
- Mower zones card: https://github.com/Sdahl1234/sunseeker-zone-card
- Mower map-edit card: https://github.com/Sdahl1234/sunseeker-map-edit-card

# Entities new models (wireless) 
Not all are availeble for V models
## Lawn mower
#### States
- Going home
- Charging
- Standby
- Working
- Pause
- Error
- Returning
- Returning paused
- Charged
- Offline
- Locating
- Stoped
- Continue mowing
- Stuck
- Updating firmware
#### Actions
- **Start** - Starts the mower
- **Pause** - Pause the mower
- **Stop** - Stops the mower
- **Home**  - Sending the mower home
## Buttons
- **Start** - Starts the mower
- **Home** - Sending the mower home
- **Pause** - Pause the mower
- **Stop** - Stops the mower
- **End task** - Ends the current task
## Consumable items
- **Buttons**
  - **Reset blade** - Resets the blade healt to 100%
  - **Reset bladplate** - Resets the bladeplade healt to 100%
- **Sensors**
  - **Blade healt** - Blade healt in %
  - **Blade change** - Time left to change blade
  - **Bladeplate healt** - Bladeplate healt in %
  - **Bladepate cleaning** - Time left to cleaning bladeplade
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
## Global sensors
- **Progress** - progress of the current mowing cycle
- **Total area** - Total area of your map
- **Coverd area** - The amount of area covered
- **Battery** - Battery percentage
- **Actual mowingtime** - Time the mower has mowed
- **Online** - Connected or Disconnected
- **Wifi strength** - The strength of the wifi signal
- **Event** - Events and codes (todo: Map events to real text)
- **Robot signal** - Signalstrength to mower
- **4G Net strength** - 4G network strength if you have a sim module
- **Zones** - Dropdown with all zones
## Global settings
- **Settings**
  - **Avoiding objects** - No touch, Slow touch
  - **AI Sensitivity** - Low, High
  - **Edge trim frequency** - Everytime, Every 2nd time, Every 3rd time
  - **Edge first** - Cut edge first or last
  - **Cutting gap** - Narrow, Normal, Wide
  - **Cutting pattern** - Standard, Change pattern, User defined
  - **Work speed** - Slow, Normal, Fast
  - **Cutting angle** - Setting the cutting angle if Cutting pattern is User defined
  - **Blade speed** - Speed of the blades
  - **Blade height** - Height of the blades
  - **User defined zones** - If enabled the zone settings will be used
    
## Zones - for each zone on your map you will have the following enteties
- **Sensors**
  - **{zonename}Estimated time** - Estimated time to mowe the area
  - **{zonename}Area** - Area size
- **Settings**
  - **{zonename}Cutting gap** - Narrow, Normal, Wide
  - **{zonename}Cutting pattern** - Standard, Change pattern, User defined
  - **{zonename}Work speed** - Slow, Normal, Fast
  - **{zonename}Cutting angle** - Setting the cutting angle if Cutting pattern is User defined
  - **{zonename}Blade speed** - Speed of the blades
  - **{zonename}Blade height** - Height of the blades
- Easy way to control the zones is using the zone card https://github.com/Sdahl1234/sunseeker-zone-card
<img width="1004" height="853" alt="image" src="https://github.com/user-attachments/assets/e5e50298-bd6f-44fe-b570-79ac30f8e55d" />

## Schedule
- **Pause schedule** - Turns on/off the schedule
- **Repeat time work** - If enabled the mower continues mowing after end cycle
- **Schedule** - Sensor with attribues containing the schedule. This is the one you must use in the schedule card https://github.com/Sdahl1234/sunseeker-schedule-card
<img width="905" height="854" alt="image" src="https://github.com/user-attachments/assets/f8674bcc-1afd-4ef4-9890-8c9e57b1ca72" />


## Map
- **map** - Image of the map - Use this one in the sunseeker-map-edit-card
- **Live map** - Camera entity of Live Map with mower movments
- **Heat map** - image of the heat map
- **Wifi map** - Image of the wifimap

## Mower Map edit card
https://github.com/Sdahl1234/sunseeker-map-edit-card
<img width="1612" height="539" alt="image" src="https://github.com/user-attachments/assets/c7018b9c-1d94-495f-b47d-ab00c1029020" />

## Mower control card
https://github.com/Sdahl1234/sunseeker-mower-control-card
<img width="901" height="714" alt="image" src="https://github.com/user-attachments/assets/78235dbd-8555-4bed-b386-7da1a846735f" />

## Device tracker
- **Mower location** - Anti theft location. Returns the latitude and longitude coordinates of the device.

## Device update
- **Notification** - Notification when mower or basestation has firmware updates**

## Actions
- **Change pin** - Action to change pin code
- **Start mowing** - Action to start the mower
- **Stop mowing** - Action to stop the mower
- **Set Schedule** - Action to set the schedule
- **Set map** - Action to update the current map
- **Delete backup** - Action to delete backedup map
- **Restore map** - Action to restore map from backup
- **Backup map** - Action to backup current map
- **Start mowing selected area** - Action to start mowing a custom area
- **Stop task** - Action to stop current task
- **Change PIN** - Action to change PIN code

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

## Device tracker
- **Robot location** - Some kind of anti theft thing. Returns the latitude and longitude coordinates of the device.
