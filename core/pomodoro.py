import time

work_time = 25 #minutes
short_break = 5
long_break = 15

current_min = 0
current_sec = 0

cycle = 0

class Timer:
    def __init__(self, work_time, short_break, long_break):
        self.work_time = work_time
        self.short_break = short_break
        self.long_break = long_break

    def start(self):
        while True:
            self.countdown(self.work_time * 60)
            print("rest")
            if cycle % 4 == 0:
                self.countdown(self.long_break * 60)
            else:
                self.countdown(self.short_break * 60)
            print("work")
            cycle += 1

    def countdown(self, seconds):
        while seconds:
            mins, secs = divmod(seconds, 60)
            timeformat = '{:02d}:{:02d}'.format(mins, secs)
            print(timeformat, end='\r')
            time.sleep(1)
            seconds -= 1
