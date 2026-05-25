import time


def main() -> None:
    print("LectureLens Python engine ready", flush=True)
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print("LectureLens engine stopping", flush=True)


if __name__ == "__main__":
    main()
