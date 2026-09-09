export default function PlaceholderPage({ eyebrow, title, text }) {
  return <section className="placeholder page-container"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{text}</p><span className="placeholder-sticker">Coming next</span></section>
}
