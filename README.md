# Sunseeker lawn mower integration for Home Assistant
Home assistant integration from lawnmower using the robotic-mower connect APP.

## Tested models
  - Adano RM6
  - Brücke RM501

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
You must now choose a barnd and a name for the device. Email and password for the robotic-mower connect APP.

## Translation
English, Danish and Finnish

# Entities
## lawn mower
#### states
Standby, Mowing, Going home, Charging, Border, Error

***Note*** The state is **NOT** following the standard states for lawnmower entity. The standar has only: START_MOWING, PAUSE and DOCK
#### Actions
**Start** - Starts the mower

**Pause** - Pause the mower

**Home**  - Sending the mower home

## buttons
**Start** - Starts the mower

**Home** - Sending the mower home

**Pause** - Pause the mower

**Border** - If the mower is in the dock it will mowe the border

## Switches
**Rain sensor** - Turn on/off the rain sensor

**Multizone** - Turn on/off using zones

**Multizone auto** - Turn on/off auto multizone

## Numbers
**Rain delay** - Minutes from when the rain sensor is dry to start mowing again

**Zone 1** - percentage of the start of zone 1

**Zone 2** - percentage of the start of zone 2

**Zone 3** - percentage of the start of zone 3

**Zone 4** - percentage of the start of zone 4

## Text
*Format of the text fields: Start and end time format HH:MM. Add Trim to mowe the border. ex. "06:15 - 17:00 Trim", "06:15 - 17:00", "08:00 - 24:00" or whole day "00:00 - 24:00"*

**Schedule Monday** - Text field to update the moday schedule. 

**Schedule Tuesday** - Text field to update the moday schedule. 

**Schedule Wednesday** - Text field to update the moday schedule. 

**Schedule Thursday** - Text field to update the moday schedule. 

**Schedule Friday** - Text field to update the moday schedule. 

**Schedule Saturday** - Text field to update the moday schedule. 

**Schedule Sunday** - Text field to update the moday schedule. 

## Binary sensors
**Dock** - states: home or away

**Rain sensor active** - on/off

**Multizone** - on/off

**Multizone auto** - on/off

**Online** - Connected (the robot is turn on an conneced to wifi) / Disconnected

## Sensors
**Battery** - Percentage of the battery

**Mower** state - Same state af the mower entity

**Wifi level** - 0, 1, 2 or 3

**State change error** - Return the error message if any, whene changing the settings. ex. "The mower is offline" 

**Rain sensor status** - Dry, Dry countdown, Wet

**Rain sensor delay** - Same as the number entity

**Rain sensor countdown** - The time left before starting mowing again

**Actual mowingtime** - The time the mower has been mowing since last charge

**Zone1,2,3,4** - Same as the number entity

**Error** - error text returned for the mower

**Errorcode** - The errorcode returned for the mower

**Schedule** - The state is always schedule, and contains the schedule settings as attributes.

## Device tracker
**Robot location** - Some kind of anti theft thing. Returns the latitude and longitude coordinates of the device.
