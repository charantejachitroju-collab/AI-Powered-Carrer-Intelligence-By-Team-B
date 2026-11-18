import { FileText, LoaderCircle } from "lucide-react";

export function Card({ children, className = "", as: Element = "section", ...props }) {
  return <Element className={`glass-card ${className}`} {...props}>{children}</Element>;
}

export function Button({ children, className = "", variant = "primary", loading = false, disabled = false, ...props }) {
  return <button
    className={`ui-button ui-button-${variant} ${className}`}
    aria-busy={loading || undefined}
    disabled={loading || disabled}
    {...props}
  >
    {loading && <LoaderCircle size={16} className="animate-spin" aria-hidden="true"/>}
    {children}
  </button>;
}

export function TextInput({ label, className = "", id, error, ...props }) {
  return <label className="ui-field" htmlFor={id}>
    <span>{label}</span>
    <input id={id} className={`ui-input ${className}`} aria-invalid={error ? "true" : undefined} {...props}/>
    {error && <small className="ui-field-error" role="alert">{error}</small>}
  </label>;
}

export function SelectInput({ label, options, className = "", id, error, ...props }) {
  return <label className="ui-field" htmlFor={id}>
    <span>{label}</span>
    <select id={id} className={`ui-input ${className}`} aria-invalid={error ? "true" : undefined} {...props}>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
    {error && <small className="ui-field-error" role="alert">{error}</small>}
  </label>;
}

export function TextArea({ label, className = "", id, error, ...props }) {
  return <label className="ui-field" htmlFor={id}>
    <span>{label}</span>
    <textarea id={id} className={`ui-input ui-textarea ${className}`} aria-invalid={error ? "true" : undefined} {...props}/>
    {error && <small className="ui-field-error" role="alert">{error}</small>}
  </label>;
}

export function EmptyState({ icon: Icon = FileText, title, description, action, className = "" }) {
  return <div className={`empty-state ${className}`}>
    <span className="empty-state-icon" aria-hidden="true"><Icon size={22}/></span>
    <h3>{title}</h3>
    <p>{description}</p>
    {action && <div className="empty-state-action">{action}</div>}
  </div>;
}

export function Loading({ label = "Loading…" }) {
  return <div className="ui-loading" role="status"><LoaderCircle size={18} className="animate-spin"/><span>{label}</span></div>;
}
