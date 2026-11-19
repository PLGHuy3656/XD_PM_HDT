function AutomaticRulesPanel({
  zone,
  rules,
  disabled = false,
  isConnected = false,
  unavailableMessage = null,
  onRuleChange,
  onSave,
}) {
  const effectiveZone = zone || {}
  const effectiveRules = rules || {
    temperature: { min: 27, max: 31 },
    humidity: { min: 75, max: 90 },
  }
  const hasControllerSync =
    isConnected &&
    Boolean(effectiveZone.controller) &&
    effectiveZone.controller !== 'Chưa kết nối'

  return (
    <section className="automatic-rules-card" aria-label="Quy tắc điều khiển tự động">
      <div className="automatic-rules-header">
        <div>
          <span className="control-mini-label">AUTO RULES · {effectiveZone.name || 'Khu vực'}</span>
          <h3>Ngưỡng điều khiển tự động</h3>
        </div>

        <span
          className={`rule-sync-badge ${hasControllerSync ? '' : 'rule-sync-badge--unsynced'}`.trim()}
        >
          {hasControllerSync
            ? `Đồng bộ với ${effectiveZone.controller}`
            : 'Chưa xác minh đồng bộ ESP32'}
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
                  disabled={disabled}
                  value={effectiveRules?.temperature?.min ?? 27}
                  onChange={(event) =>
                    onRuleChange?.('temperature', 'min', event.target.value)
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
                  disabled={disabled}
                  value={effectiveRules?.temperature?.max ?? 31}
                  onChange={(event) =>
                    onRuleChange?.('temperature', 'max', event.target.value)
                  }
                />
                <b>°C</b>
              </div>
            </label>
          </div>

          <div className="rule-behaviour">
            <span>AUTO BEHAVIOUR</span>
            <strong>Sưởi khi thấp · Thông gió khi cao</strong>
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
                  disabled={disabled}
                  value={effectiveRules?.humidity?.min ?? 75}
                  onChange={(event) =>
                    onRuleChange?.('humidity', 'min', event.target.value)
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
                  disabled={disabled}
                  value={effectiveRules?.humidity?.max ?? 90}
                  onChange={(event) =>
                    onRuleChange?.('humidity', 'max', event.target.value)
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
            {unavailableMessage ||
              'Ngưỡng mới sẽ đồng bộ xuống bộ điều khiển ESP32 và chỉ có hiệu lực sau khi nhận ACK.'}
          </p>
        </div>

        <button type="button" disabled={disabled} onClick={onSave}>
          Lưu cấu hình
        </button>
      </div>
    </section>
  )
}

export default AutomaticRulesPanel
