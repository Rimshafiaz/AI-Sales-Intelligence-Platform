import { domainOf, type Citation, type Finding } from '../../lib/report'

function CitationMark({
  citation,
  number,
}: {
  citation: Citation
  number: number
}) {
  const domain = domainOf(citation.source_url)
  const tooltip = citation.supporting_excerpt
    ? `${domain}: ${citation.supporting_excerpt}`
    : domain

  return (
    <a
      href={citation.source_url}
      target="_blank"
      rel="noreferrer"
      title={tooltip}
      className="align-super font-mono text-[10px] font-medium text-action hover:underline"
    >
      [{number}]
    </a>
  )
}

export function FindingText({
  finding,
  citationIndex,
  className = '',
  variant = 'ui',
}: {
  finding: Finding
  citationIndex: Map<string, number>
  className?: string
  variant?: 'ui' | 'narrative'
}) {
  const textFont =
    variant === 'narrative'
      ? 'font-narrative text-sm leading-relaxed'
      : 'font-ui text-sm leading-snug'
  return (
    <div className={className}>
      <p className={textFont + ' text-justify text-ink'}>
        {finding.statement}
        {finding.citations.map((citation) => {
          const number = citationIndex.get(citation.source_url.replace(/\/+$/, ''))
          return number ? (
            <CitationMark key={citation.source_url} citation={citation} number={number} />
          ) : null
        })}
        {finding.is_inference && (
          <span className="ml-1.5 inline-block rounded-[2px] border border-inference-edge bg-inference-bg px-1 font-display text-[9px] font-semibold uppercase tracking-wide text-inference-ink align-middle">
            Inference
          </span>
        )}
      </p>
      {finding.is_inference && (
        <details className="mt-1">
          <summary className="cursor-pointer select-none font-ui text-[11px] font-medium text-action hover:text-ink">
            Reasoning
          </summary>
          <p className="mt-0.5 border-l-2 border-line pl-2 text-xs italic leading-relaxed text-ink-soft">
            {finding.rationale}
          </p>
        </details>
      )}
    </div>
  )
}
