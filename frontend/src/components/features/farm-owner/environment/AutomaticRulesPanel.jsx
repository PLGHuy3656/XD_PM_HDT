function AutomaticRulesPanel({
  zone,
  rules,
  onRuleChange,
  onSave,
}) {
  return (
    <section className="control-section">
      <div className="control-section-title">
        <span>02</span>

        <div>
          <small>AUTOMATIC RULES</small>
          <h2>Quy tắc điều khiển tự động</h2>
          <p>
            Cấu hình khoảng môi trường mà controller sử dụng trong chế độ AUTO.
          </p>
        </div>
      </div>

      <div className="automatic-rules-card">
        <div className="automatic-rules-header">
          <div>
            <span className="control-mini-label">LOCAL RULE SET</span>
            <h3>{zone.name}</h3>
          </div>

          <span className="rule-sync-badge">
            Đồng bộ với {zone.controller}
          </span>
        </div>

        <div className="rule-list">
          <div className="rule-row">
            <div className="rule-identity temperature">
              <span className="rule-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M9 14.5V5a3 3 0 0 1 6 0v9.5a5 5 0 1 1-6 0Z" />
                  <path d="M12 17V8" />
                </svg>
              </span>

              <div>
                <strong>Nhiệt độ</strong>
                <small>Temperature range</small>
              </div>
            </div>

            <div className="rule-range">
              <label>
                <span>Tối thiểu</span>

                <div>
                  <input
                    type="number"
                    value={rules.temperature.min}
                    onChange={(event) =>
                      onRuleChange(
                        'temperature',
                        'min',
                        event.target.value
                      )
                    }
                  />

                  <b>°C</b>
                </div>
              </label>

              <span className="range-line" />

              <label>
                <span>Tối đa</span>

                <div>
                  <input
                    type="number"
                    value={rules.temperature.max}
                    onChange={(event) =>
                      onRuleChange(
                        'temperature',
                        'max',
                        event.target.value
                      )
                    }
                  />

                  <b>°C</b>
                </div>
              </label>
            </div>

            <div className="rule-behaviour">
              <span>AUTO BEHAVIOUR</span>
              <strong>
                Sưởi khi thấp · Thông gió khi cao
              </strong>
            </div>
          </div>

          <div className="rule-row">
            <div className="rule-identity humidity">
              <span className="rule-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3s-6 6.5-6 11a6 6 0 0 0 12 0c0-4.5-6-11-6-11Z" />
                </svg>
              </span>

              <div>
                <strong>Độ ẩm</strong>
                <small>Humidity range</small>
              </div>
            </div>

            <div className="rule-range">
              <label>
                <span>Tối thiểu</span>

                <div>
                  <input
                    type="number"
                    value={rules.humidity.min}
                    onChange={(event) =>
                      onRuleChange(
                        'humidity',
                        'min',
                        event.target.value
                      )
                    }
                  />

                  <b>%</b>
                </div>
              </label>

              <span className="range-line" />

              <label>
                <span>Tối đa</span>

                <div>
                  <input
                    type="number"
                    value={rules.humidity.max}
                    onChange={(event) =>
                      onRuleChange(
                        'humidity',
                        'max',
                        event.target.value
                      )
                    }
                  />

                  <b>%</b>
                </div>
              </label>
            </div>

            <div className="rule-behaviour">
              <span>AUTO BEHAVIOUR</span>
              <strong>Phun sương khi độ ẩm thấp</strong>
            </div>
          </div>
        </div>

        <div className="automatic-rules-footer">
          <div>
            <span className="rules-info-icon">i</span>

            <p>
              Đây là dữ liệu mock ở Frontend. Khi tích hợp, Backend sẽ lưu cấu
              hình và đồng bộ xuống ESP32.
            </p>
          </div>

          <button type="button" onClick={onSave}>
            Lưu cấu hình
          </button>
        </div>
      </div>
    </section>
  )
}

export default AutomaticRulesPanel