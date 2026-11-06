const steps = [
  {
    id: 1,
    label: 'Vị trí',
  },
  {
    id: 2,
    label: 'Thiết bị',
  },
  {
    id: 3,
    label: 'Cấu hình',
  },
  {
    id: 4,
    label: 'Kiểm tra',
  },
  {
    id: 5,
    label: 'Hoàn tất',
  },
]

function InstallationProgress({
  currentStep,
  onStepChange,
}) {
  return (
    <div className="installation-progress">
      {steps.map((step) => {
        const active = step.id === currentStep
        const completed = step.id < currentStep
        const accessible = step.id <= currentStep

        return (
          <button
            type="button"
            key={step.id}
            className={`installation-progress__step ${
              active ? 'is-active' : ''
            } ${
              completed ? 'is-completed' : ''
            }`}
            disabled={!accessible}
            onClick={() => {
              if (accessible) {
                onStepChange(step.id)
              }
            }}
          >
            <span className="installation-progress__number">
              {completed ? '✓' : step.id}
            </span>

            <span>{step.label}</span>
          </button>
        )
      })}
    </div>
  )
}

export default InstallationProgress