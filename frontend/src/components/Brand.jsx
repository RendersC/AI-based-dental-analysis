import './Brand.css'

export default function Brand({ size = 'sm', as = 'div', href }) {
  const className = `brand brand--${size}`
  const content = (
    <>
      <img className="brand__logo" src="/logo-mark.svg" alt="" aria-hidden="true" />
      <span className="brand__name">Радуга&nbsp;Улыбок</span>
    </>
  )
  if (href) {
    return (
      <a className={className} href={href} aria-label="Радуга Улыбок — на главную">
        {content}
      </a>
    )
  }
  const Tag = as
  return <Tag className={className} aria-label="Радуга Улыбок">{content}</Tag>
}
