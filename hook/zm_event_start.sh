#!/bin/bash

trap 'cleanup' SIGINT SIGTERM

# Handle situation of ZM terminates while this is running
# so notifications are not sent
cleanup() {
   # Don't echo anything here
   exit 1
}

# When invoked by zmeventnotification.pl it will be passed:
# $1 = eventId that triggered an alarm
# $2 = monitor ID of monitor that triggered an alarm
# $3 = monitor Name of monitor that triggered an alarm
# $4 = cause of alarm 
# $5 = path to event store (if store_frame_in_zm is 1)



# Only tested with ZM 1.32.3+. May or may not work with older versions
# Logic:
# This script is invoked by zmeventnotification is you've specified its location in the hook= variable of zmeventnotification.pl


# change this to the path of the object detection config"
CONFIG_FILE="/etc/zm/objectconfig.ini"
EVENT_PATH="$5"
REASON="$4"


# use arrays instead of strings to avoid quote hell
if [[ ! -z "${2}" ]]
then 
   DETECTION_SCRIPT=(/var/lib/zmeventnotification/bin/zm_detect.py --monitorid $2 --eventid $1 --config "${CONFIG_FILE}" --eventpath "${EVENT_PATH}" --reason "${REASON}"  )
else
   DETECTION_SCRIPT=(/var/lib/zmeventnotification/bin/zm_detect.py  --eventid $1 --config "${CONFIG_FILE}" --eventpath "${EVENT_PATH}" --reason "${REASON}"  )

fi
RESULTS=$("${DETECTION_SCRIPT[@]}" | grep "detected:")

_RETVAL=1
# The script needs  to return a 0 for success ( detected) or 1 for failure (not detected)
if [[ ! -z "${RESULTS}" ]]; then
   _RETVAL=0 
fi

CHECK_RESULTS=$(/var/lib/zmeventnotification/contrib/check_event_and_cleanup.py ${_RETVAL} $1 $2 '' "${REASON} ${RESULTS}" '' "${EVENT_PATH}" 0 | grep "INTERESTING")
if [[ -z "${CHECK_RESULTS}" ]]; then
  # Note that the "detected" message in the event note will disappear due to
  # this, but that is okay
  _RETVAL=1
fi

echo ${RESULTS}
exit ${_RETVAL}
