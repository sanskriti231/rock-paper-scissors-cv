import cv2

cap = cv2.VideoCapture(0)

while True:
    success, frame = cap.read()

    if not success:
        print("Could not access camera")
        break

    cv2.imshow("Rock paper scissors", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    try:
        if cv2.getWindowProperty(
            "Rock Paper Scissors",
            cv2.WND_PROP_VISIBLE
        ) < 1:
            break
    except cv2.error:
        break

cap.release()
cv2.destroyAllWindows()