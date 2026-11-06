import { useState } from 'react'
import { systemSettings } from './systemMockData'

function SystemSettings() {
  const [settings, setSettings] =
    useState(systemSettings)

  const [draft, setDraft] = useState(settings)
  const [editing, setEditing] = useState(false)

  function startEditing() {
    setDraft(settings)
    setEditing(true)
  }

  function cancelEditing() {
    setDraft(settings)
    setEditing(false)
  }

  function handleChange(section, field, value) {
    setDraft((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: Number(value),
      },
    }))
  }

  function handleSave() {
    setSettings(draft)
    setEditing(false)
  }

  return (
    <section className="admin-system-card">
      <div className="admin-system-card__heading">
        <div>
          <span>SYSTEM SETTINGS</span>
          <h2>Cấu hình mặc định</h2>
          <p>
            Giá trị mặc định áp dụng khi Farm chưa có cấu
            hình riêng.
          </p>
        </div>

        {!editing && (
          <button
            type="button"
            className="admin-system-primary-button"
            onClick={startEditing}
          >
            Chỉnh sửa cấu hình
          </button>
        )}
      </div>

      <div className="admin-system-settings-grid">
        <article>
          <span>Nhiệt độ mặc định</span>

          <div className="admin-system-setting-values">
            <label>
              Min
              <input
                type="number"
                value={
                  editing
                    ? draft.temperature.min
                    : settings.temperature.min
                }
                disabled={!editing}
                onChange={(event) =>
                  handleChange(
                    'temperature',
                    'min',
                    event.target.value,
                  )
                }
              />
            </label>

            <span>—</span>

            <label>
              Max
              <input
                type="number"
                value={
                  editing
                    ? draft.temperature.max
                    : settings.temperature.max
                }
                disabled={!editing}
                onChange={(event) =>
                  handleChange(
                    'temperature',
                    'max',
                    event.target.value,
                  )
                }
              />
            </label>

            <strong>°C</strong>
          </div>
        </article>

        <article>
          <span>Độ ẩm mặc định</span>

          <div className="admin-system-setting-values">
            <label>
              Min
              <input
                type="number"
                value={
                  editing
                    ? draft.humidity.min
                    : settings.humidity.min
                }
                disabled={!editing}
                onChange={(event) =>
                  handleChange(
                    'humidity',
                    'min',
                    event.target.value,
                  )
                }
              />
            </label>

            <span>—</span>

            <label>
              Max
              <input
                type="number"
                value={
                  editing
                    ? draft.humidity.max
                    : settings.humidity.max
                }
                disabled={!editing}
                onChange={(event) =>
                  handleChange(
                    'humidity',
                    'max',
                    event.target.value,
                  )
                }
              />
            </label>

            <strong>%</strong>
          </div>
        </article>

        <article>
          <span>Alert cooldown</span>

          <div className="admin-system-single-setting">
            <input
              type="number"
              value={
                editing
                  ? draft.alertCooldown
                  : settings.alertCooldown
              }
              disabled={!editing}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  alertCooldown: Number(
                    event.target.value,
                  ),
                }))
              }
            />

            <strong>phút</strong>
          </div>
        </article>

        <article>
          <span>Ngưỡng offline thiết bị</span>

          <div className="admin-system-single-setting">
            <input
              type="number"
              value={
                editing
                  ? draft.offlineThreshold
                  : settings.offlineThreshold
              }
              disabled={!editing}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  offlineThreshold: Number(
                    event.target.value,
                  ),
                }))
              }
            />

            <strong>phút</strong>
          </div>
        </article>
      </div>

      {editing && (
        <div className="admin-system-settings-actions">
          <button
            type="button"
            onClick={cancelEditing}
          >
            Hủy
          </button>

          <button
            type="button"
            className="admin-system-primary-button"
            onClick={handleSave}
          >
            Lưu cấu hình
          </button>
        </div>
      )}

      <div className="admin-system-settings-note">
        <strong>Phạm vi cấu hình</strong>
        <p>
          Đây là cấu hình mặc định ở cấp hệ thống. Farm có
          thể sử dụng ngưỡng riêng khi Backend hỗ trợ cấu
          hình theo Farm/Zone.
        </p>
      </div>
    </section>
  )
}

export default SystemSettings