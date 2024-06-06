#!/usr/bin/python3

'''Author: Gabriel Hjort Åkerlund <gabriel@hjort.dev> <github.com/gablin>

Intended trigger: event_end_hook

Description:
  Checks if the event has any (detected) objects.

Arguments:
  1: End hook result - expect this to always be 0
  2: Event ID
  3: Monitor ID
  4: Monitor Name
  5: alarm cause
  6: alarm cause JSON string - expect this to always be empty
  7: event path (if hook_pass_image_path is yes)
  8: In end phase (0/1; optional, 1 default)

'''

import datetime
import json
import requests
import subprocess


#==========
# SETTINGS
#==========

ALARM_STATE_FILE = '/etc/alarm-status-server/alarm_state'
PUSHOVER_FILE = '/etc/zm/pushover.json'
FRONT_MONITOR_ID = '8'
SNAPSHOT_PATH = '/tmp/snapshot_{}.jpg'


#===========
# FUNCTIONS
#===========

def fail(logger, msg):
  logger.Error(msg)
  sys.exit(1)

PUSHOVER_CONFIG = None
def readPushOverConfig():
  global PUSHOVER_CONFIG

  with open(PUSHOVER_FILE, 'r') as fp:
    PUSHOVER_CONFIG = json.load(fp)

def fromPushOverConfig(logger, key, fail_if_missing = True):
  global PUSHOVER_CONFIG

  if not key in PUSHOVER_CONFIG:
    if fail_if_missing:
      fail(logger, 'Key missing in config: {}'.format(key))
    else:
      return None
  return PUSHOVER_CONFIG[key]

def invokeCommand(logger, cmd):
  logger.Debug(2, 'Invoking command: {}'.format(cmd))
  res = subprocess.run(cmd, capture_output=True)
  logger.Debug(2, '- Return code: {}'.format(res.returncode))
  return res

def takeSnapshot(logger):
  logger.Info('Taking snapshot...')
  path = EVENT_PATH + '/objdetect.jpg'
  logger.Debug(2, 'Snapshot path: {}'.format(path))
  return path

def sendNotification(logger, snapshot_path, title, msg, priority):
  logger.Info('Sending notification...')
  pushover_data = { 'token': fromPushOverConfig(logger, 'pushover_api_token')
                  , 'user': fromPushOverConfig(logger, 'pushover_user_key')
                  , 'title': title
                  , 'message': msg
                  , 'priority': priority
                  , 'sound': fromPushOverConfig(logger, 'pushover_sound')
                  }
  pushover_image = { 'attachment': ( 'image.jpg'
                                   , open(snapshot_path, 'rb')
                                   , 'image/jpeg'
                                   )
                   } if snapshot_path else {}
  res = requests.post( 'https://api.pushover.net/1/messages.json'
                     , data = pushover_data
                     , files = pushover_image
                     )
  logger.Debug(2, 'Sent')
  if res.status_code != 200:
    logger.Error('Failed to send message: {}'.format(res.text))

def isEventInteresting(logger):
  # Read alarm state
  with open(ALARM_STATE_FILE, 'r') as fh:
    alarm_state = fh.read().strip()

  if CAUSE_S.find('ALARM') >= 0:
    logger.Info('Event {}: Triggered by ALARM'.format(EVENT_ID))
    return True
  elif CAUSE_S.find('DOOR BELL') >= 0:
    logger.Info('Event {}: Triggered by DOOR BELL'.format(EVENT_ID))
    return True
  elif CAUSE_S.find('Motion') >= 0:
    logger.Info('Event {}: Triggered by MOTION'.format(EVENT_ID))
  else:
    logger.Info('Event {}: Triggered by UNKNOWN cause'.format(EVENT_ID))
    return True


  if CAUSE_S.find('detected:person') >= 0:
    logger.Info('Event {}: DETECTED person(s)'.format(EVENT_ID))
    readPushOverConfig()
    movement_is_on_front = MONITOR_ID == FRONT_MONITOR_ID
    msg = 'Någon rör sig på framsidan' if movement_is_on_front else 'Någon rör sig på baksidan'
    if alarm_state == '0' or movement_is_on_front:
      is_movement_on_front = MONITOR_ID == FRONT_MONITOR_ID
      is_event_of_interest = False
      now_h = int(datetime.datetime.now().strftime('%H'))
      if is_movement_on_front and False:
        logger.Info('Event {}: NOT at night time but movement on front'.format(EVENT_ID))
        is_event_of_interest = True
      elif now_h >= 0 and now_h < 6:
        logger.Info('Event {}: AT night time'.format(EVENT_ID))
        is_event_of_interest = True
      else:
        logger.Info('Event {}: NOT at night time'.format(EVENT_ID))

      if is_event_of_interest:
        if IN_START_PHASE == '1':
          snapshot_path = takeSnapshot(logger)
          sendNotification(logger, snapshot_path, 'NOTIS', msg, 0)
        return True
    else:
      logger.Info('Event {}: Alarm is NOT inactive'.format(EVENT_ID))
      if IN_START_PHASE == '1':
        snapshot_path = takeSnapshot(logger)
        sendNotification( logger
                        , snapshot_path
                        , 'NOTIS'
                        , msg
                        , 0
                        )
      return True
  else:
    logger.Info('Event {}: NO person detected'.format(EVENT_ID))
  return False


#======
# MAIN
#======

if __name__ == "__main__":
  import argparse
  import pyzm.api as zmapi
  import pyzm.ZMLog as zmlog
  import ssl
  import sys
  import traceback
  import zmes_hook_helpers.utils as utils
  import zmes_hook_helpers.common_params as g

  HOOK_RESULT  = sys.argv[1]
  EVENT_ID     = sys.argv[2]
  MONITOR_ID   = sys.argv[3]
  MONITOR_NAME = sys.argv[4]
  CAUSE_S      = sys.argv[5]
  CAUSE_JSON   = sys.argv[6]
  EVENT_PATH   = sys.argv[7]
  IN_END_PHASE = sys.argv[8] if len(sys.argv) >= 9 else '1'
  IN_START_PHASE = '1' if IN_END_PHASE == '0' else '0'

  # Create arguments needed for setting up g
  ap = argparse.ArgumentParser()
  ap.add_argument('--config', default='/etc/zm/objectconfig.ini')
  args, _ = ap.parse_known_args()
  args = vars(args)

  # Set up g
  zmlog.init(name='zmescleanup_m{}'.format(MONITOR_ID))
  g.logger = zmlog
  utils.get_pyzm_config(args)
  g.ctx = ssl.create_default_context()
  utils.process_config(args, g.ctx)
  try:
    if isEventInteresting(g.logger):
      print('INTERESTING')
    else:
      print('USELESS')
      if IN_END_PHASE == '1':
        g.logger.Info('Deleting event {}'.format(EVENT_ID))

        # Connect to ZM API
        api_options = \
          { 'apiurl': g.config['api_portal']
          , 'portalurl': g.config['portal']
          , 'user': g.config['user']
          , 'password': g.config['password']
          , 'basic_auth_user': g.config['basic_user']
          , 'basic_auth_password': g.config['basic_password']
          , 'logger': g.logger
          , 'disable_ssl_cert_check':
              False if g.config['allow_self_signed']=='no' else True
          }
        g.logger.Info('Connecting with ZM APIs')
        zmapi = zmapi.ZMApi(options=api_options)

        url = '{}/events/{}.json'.format(g.config['api_portal'], EVENT_ID)
        try:
          zmapi._make_request(url=url, type='delete')
        except ValueError as e:
          if str(e) == 'BAD_IMAGE':
            pass # This is often received; don't know why so ignore it
          else:
            raise e
  except Exception as e:
    g.logger.Error(str(e))
    g.logger.Debug(2, traceback.format_exc())
