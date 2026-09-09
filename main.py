from core.pomodoro import Timer, long_break, short_break, work_time

def main():
    Timer(work_time, short_break, long_break).start()

if __name__ == "__main__":
    main()