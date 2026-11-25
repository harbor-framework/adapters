You are operating an Android phone (a Pixel 6 emulator, Android 13) that is running inside this container. Complete the following task on the phone:

{goal}

## How to interact with the phone

- The emulator is started automatically and the task state is prepared for you. If `adb devices` shows no device, run `/opt/aw/boot.sh` and then `python3 /opt/aw/client.py wait` (this can take a few minutes).
- Use `adb` (device `emulator-5554`) to observe and control the phone, for example:
  - screenshot: `adb exec-out screencap -p > /tmp/screen.png`
  - UI hierarchy: `adb shell uiautomator dump /sdcard/ui.xml && adb shell cat /sdcard/ui.xml`
  - tap / swipe / type / keys: `adb shell input tap X Y`, `adb shell input swipe X1 Y1 X2 Y2`, `adb shell input text 'hello'`, `adb shell input keyevent KEYCODE_BACK`
- The phone's date/time is fixed by the benchmark; do not change it.
{answer_note}
The task is evaluated from the final state of the phone (and the answer file, if one is required), so leave the phone in the state described by the task.
