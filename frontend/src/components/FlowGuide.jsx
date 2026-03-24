export default function FlowGuide({ icon, title, steps }) {
  return (
    <div className="flow-guide">
      <div className="flow-guide-icon">{icon}</div>
      <div className="flow-guide-title">{title}</div>
      {steps && (
        <div
          className="flow-guide-steps"
          dangerouslySetInnerHTML={{ __html: steps }}
        />
      )}
    </div>
  )
}
