import { useState } from 'react'
import EnvironmentSelect from '../../../ui/Select'

function DetectionBox({
  className,
  label,
  confidence,
}) {
  return (
    <div className={`swiftlet-detection-box ${className}`}>
      <span>
        {label} · {confidence}%
      </span>
    </div>
  )
}

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 7.5 8.5 5h7L17 7.5" />
      <rect x="4" y="7.5" width="16" height="11" rx="2" />
      <circle cx="12" cy="13" r="3.2" />
    </svg>
  )
}

function ArrowIcon({ direction }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {direction === 'left' ? (
        <path d="m15 18-6-6 6-6" />
      ) : (
        <path d="m9 6 6 6-6 6" />
      )}
    </svg>
  )
}

function LiveCameraCard({
  cameras,
  selectedCameraId,
  onCameraChange,
}) {
  const [showBoxes, setShowBoxes] = useState(true)

  const selectedCamera =
    cameras.find((camera) => camera.id === selectedCameraId) ??
    cameras[0]

  const currentIndex = cameras.findIndex(
    (camera) => camera.id === selectedCamera.id,
  )

  const isOnline = selectedCamera.status === 'ONLINE'

  function moveCamera(offset) {
    const nextIndex =
      (currentIndex + offset + cameras.length) % cameras.length

    onCameraChange(cameras[nextIndex].id)
  }

  return (
    <section className="swiftlet-card swiftlet-camera-card">
      <div className="swiftlet-card-heading swiftlet-camera-heading">
        <div>
          <div className="swiftlet-live-title">
            <i className={isOnline ? '' : 'offline'} />
            <h2>Camera AI trực tiếp</h2>
          </div>

          <p>
            {selectedCamera.zoneName} · {selectedCamera.name}
          </p>
        </div>

        <div className="swiftlet-camera-controls">
          <div className="swiftlet-camera-switcher">
            <button
              type="button"
              className="swiftlet-camera-arrow"
              onClick={() => moveCamera(-1)}
              aria-label="Camera trước"
            >
              <ArrowIcon direction="left" />
            </button>

            <EnvironmentSelect
            value={selectedCamera.id}
            onChange={onCameraChange}
            options={cameras.map((camera) => ({
                value: camera.id,
                label: `${camera.id} · ${camera.name}${
                camera.status === 'OFFLINE' ? ' · Offline' : ''
                }`,
            }))}
            />

            <button
              type="button"
              className="swiftlet-camera-arrow"
              onClick={() => moveCamera(1)}
              aria-label="Camera tiếp theo"
            >
              <ArrowIcon direction="right" />
            </button>
          </div>

          <label className="swiftlet-box-toggle">
            <input
              type="checkbox"
              checked={showBoxes}
              disabled={!isOnline}
              onChange={(event) =>
                setShowBoxes(event.target.checked)
              }
            />

            <span>Khung nhận diện</span>
          </label>
        </div>
      </div>

      <div
        className={`swiftlet-camera-view ${
          !isOnline ? 'offline' : ''
        }`}
      >
        <div className="swiftlet-camera-topbar">
          <span
            className={`swiftlet-live-badge ${
              !isOnline ? 'offline' : ''
            }`}
          >
            <i />
            {isOnline ? 'LIVE' : 'OFFLINE'}
          </span>

          <span>
            {selectedCamera.id} · {selectedCamera.name}
          </span>
        </div>

        {isOnline ? (
          <>
            <div className="swiftlet-camera-placeholder">
              <span className="swiftlet-camera-icon">
                <CameraIcon />
              </span>

              <strong>Camera trực tiếp</strong>

              <small>
                Luồng camera sẽ được kết nối từ Camera Node
              </small>
            </div>

            {showBoxes &&
              selectedCamera.detections.map((detection) => (
                <DetectionBox
                  key={detection.id}
                  className={detection.className}
                  label={detection.label}
                  confidence={detection.confidence}
                />
              ))}

            <div className="swiftlet-camera-bottom">
              <span>YOLO · Tracking</span>

              <span>
                {selectedCamera.resolution} ·{' '}
                {selectedCamera.node}
              </span>
            </div>
          </>
        ) : (
          <div className="swiftlet-camera-offline">
            <span className="swiftlet-camera-icon">
              <CameraIcon />
            </span>

            <strong>Không có tín hiệu camera</strong>

            <p>
              Không thể kết nối tới {selectedCamera.node}.
              Kiểm tra nguồn điện hoặc kết nối mạng của thiết bị.
            </p>

            <small>
              {selectedCamera.id} · {selectedCamera.zoneName}
            </small>
          </div>
        )}
      </div>
    </section>
  )
}

export default LiveCameraCard