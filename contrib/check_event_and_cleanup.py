#!/usr/bin/python3

'''Author: Gabriel Hjort Åkerlund <gabriel@hjort.dev> <github.com/gablin>

Intended trigger: event_end_hook

Description:
  Checks if the event has any (detected) objects. If not and the delete
  option is set, the event is deleted; else nothing happens.

Arguments:
  1: End hook result - expect this to always be 0
  2: Event ID
  3: Monitor ID
  4: Monitor Name
  5: alarm cause
  6: alarm cause JSON string - expect this to always be empty
  7: event path (if hook_pass_image_path is yes)
  8: Delete event flag (0/1; optional, 1 default)

'''

import datetime


#==========
# SETTINGS
#==========

ALARM_STATE_FILE = '/etc/alarm-status-server/alarm_state'


#===========
# FUNCTIONS
#===========

def isEventInteresting(logger = None):
  # Read alarm state
  with open(ALARM_STATE_FILE, 'r') as fh:
    alarm_state = fh.read().strip()

  if CAUSE_S.find('ALARM') >= 0:
    if logger:
      logger.Info('Event {}: Triggered by ALARM'.format(EVENT_ID))
    return True
  elif CAUSE_S.find('DOOR BELL') >= 0:
    if logger:
      logger.Info('Event {}: Triggered by DOOR BELL'.format(EVENT_ID))
    return False
  elif CAUSE_S.find('Motion') >= 0:
    if logger:
      logger.Info('Event {}: Triggered by MOTION'.format(EVENT_ID))
  else:
    if logger:
      logger.Info('Event {}: Triggered by UNKNOWN cause'.format(EVENT_ID))
    return True
  if CAUSE_S.find('detected:person') >= 0:
    if logger:
      logger.Info('Event {}: DETECTED person(s)'.format(EVENT_ID))
    if MONITOR_ID == '8': # Remember to update es_rules.json
      logger.Info('Event {}: ALWAYS KEEP'.format(EVENT_ID))
      return True
    if alarm_state == '0':
      if logger:
        logger.Info('Event {}: Alarm is INACTIVE'.format(EVENT_ID))
      now_h = int(datetime.datetime.now().strftime('%H'))
      if now_h >= 0 and now_h < 6:
        if logger:
          logger.Info('Event {}: AT night time'.format(EVENT_ID))
        return True
      else:
        if logger:
          logger.Info('Event {}: NOT at night time'.format(EVENT_ID))
    else:
      if logger:
        logger.Info('Event {}: Alarm is NOT inactive'.format(EVENT_ID))
      return True
  else:
    if logger:
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
  DELETE_EVENT = sys.argv[8] if len(sys.argv) >= 9 else '1'

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
  if isEventInteresting(g.logger):
    print('INTERESTING')
  else:
    print('USELESS')
    if DELETE_EVENT == '1':
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
          g.logger.Error ('Error during deletion: {}'.format(str(e)))
          g.logger.Debug(2, traceback.format_exc())
      except Exception as e:
        g.logger.Error ('Error during deletion: {}'.format(str(e)))
        g.logger.Debug(2, traceback.format_exc())
