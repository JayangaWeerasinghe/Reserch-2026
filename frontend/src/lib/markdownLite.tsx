import type { ReactNode } from 'react'

function renderInline(text: string, keyPrefix: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter((p) => p.length > 0)
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <strong key={`${keyPrefix}-b-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={`${keyPrefix}-t-${i}`}>{part}</span>
    )
  )
}

interface BulletItem {
  text: string
  indent: number
}

/** Renders the lite-markdown subset produced by the C4 chatbot: #-###### headings, **bold**, `- ` bullets (with 2-space nesting), and `---` dividers. */
export function renderLiteMarkdown(text: string): ReactNode {
  const lines = text.split('\n')
  const blocks: ReactNode[] = []
  let listBuffer: BulletItem[] = []

  function flushList(key: string) {
    if (!listBuffer.length) return
    blocks.push(
      <ul key={key} className="my-1 space-y-1">
        {listBuffer.map((item, i) => (
          <li
            key={i}
            className="leading-relaxed list-disc marker:text-amber"
            style={{ marginLeft: 16 + item.indent * 16 }}
          >
            {renderInline(item.text, `${key}-li-${i}`)}
          </li>
        ))}
      </ul>
    )
    listBuffer = []
  }

  lines.forEach((line, idx) => {
    const trimmed = line.trim()
    const bulletMatch = line.match(/^(\s*)-\s+(.*)$/)
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)

    if (trimmed === '---') {
      flushList(`hr-${idx}`)
      blocks.push(<hr key={`hr-${idx}`} className="my-2 border-beige" />)
    } else if (headingMatch) {
      // #, ##, ###, #### etc. — the LLM's report sections (Overview, Causal
      // Organism, Symptoms, ...). Sized by level; strip any optional trailing
      // "###" ATX closer.
      flushList(`h-${idx}`)
      const level = headingMatch[1].length
      const content = headingMatch[2].replace(/\s+#+$/, '')
      const headingClass =
        level <= 2
          ? 'mt-3 text-base font-bold text-forest first:mt-0'
          : level === 3
            ? 'mt-2 text-sm font-bold text-forest first:mt-0'
            : 'mt-2 text-sm font-semibold text-forest-muted first:mt-0'
      blocks.push(
        <p key={`h-${idx}`} className={headingClass}>
          {renderInline(content, `h-${idx}`)}
        </p>
      )
    } else if (bulletMatch) {
      listBuffer.push({ text: bulletMatch[2], indent: Math.floor(bulletMatch[1].length / 2) })
    } else if (trimmed === '') {
      flushList(`sp-${idx}`)
    } else if (/^\*\*.+\*\*$/.test(trimmed)) {
      // Whole line wrapped in ** — treat as a small section heading (e.g. the chemical summary header).
      flushList(`h-${idx}`)
      blocks.push(
        <p key={`h-${idx}`} className="mt-2 text-sm font-bold text-forest first:mt-0">
          {trimmed.slice(2, -2)}
        </p>
      )
    } else {
      flushList(`p-${idx}`)
      blocks.push(
        <p key={`p-${idx}`} className="leading-relaxed">
          {renderInline(trimmed, `p-${idx}`)}
        </p>
      )
    }
  })
  flushList('end')

  return <div className="space-y-1.5">{blocks}</div>
}

/** Strips the lite-markdown syntax down to plain speakable text, for the voice-output (TTS) feature. */
export function stripLiteMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*-\s+/gm, '')
    .replace(/^\s*---\s*$/gm, '')
    .replace(/[🧪💬⚠️]/gu, '')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()
}