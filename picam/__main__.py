import camera
import captures
import webserver

captures.start_processing()

camera.start_daynight_switch()
camera.start_overlay_updater()
camera.start_motion_capture()

webserver.run_webserver()

