#!/usr/bin/python3

'''Author: Gabriel Hjort Åkerlund <gabriel@hjort.dev> <github.com/gablin>

Intended trigger: event_end_hook

Description:
  Checks if the event has any (detected) objects. If not, the event is deleted;
  else nothing happens.

Arguments:
  1: End hook result - expect this to always be 0
  2: Event ID
  3: Monitor ID
  4: Monitor Name
  5: alarm cause
  6: alarm cause JSON string - expect this to always be empty
  7: event path (if hook_pass_image_path is yes)

'''

import argparse
import ssl
import sys
import pyzm.api as zmapi
import pyzm.ZMLog as zmlog
import traceback
import zmes_hook_helpers.utils as utils
import zmes_hook_helpers.common_params as g


#======
# MAIN
#======

HOOK_RESULT  = sys.argv[1]
EVENT_ID     = sys.argv[2]
MONITOR_ID   = sys.argv[3]
MONITOR_NAME = sys.argv[4]
CAUSE_S      = sys.argv[5]
CAUSE_JSON   = sys.argv[6]
EVENT_PATH   = sys.argv[7]

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

# Delete event if no persons have been detected
if CAUSE_S.find('detected:person') >= 0:
  g.logger.Info('Event {}: DETECTED person(s)'.format(EVENT_ID))
else:
  g.logger.Info('Event {}: NO person detected'.format(EVENT_ID))
  g.logger.Info('Deleting event {}'.format(EVENT_ID))
  url = '{}/events/{}.json'.format(g.config['api_portal'], EVENT_ID)
  try:
    zmapi._make_request(url=url, type='delete')
  except ValueError as e:
    if str(e) == 'BAD_IMAGE':
      pass # Ignore
    else:
      g.logger.Error ('Error during deletion: {}'.format(str(e)))
      g.logger.Debug(2, traceback.format_exc())
  except Exception as e:
    g.logger.Error ('Error during deletion: {}'.format(str(e)))
    g.logger.Debug(2, traceback.format_exc())
