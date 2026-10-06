import { Bug, Leaf } from 'lucide-react'

interface TopicChipsProps {
  topics: string[]
  onSelect: (topic: string) => void
  disabled?: boolean
}

export default function TopicChips({ topics, onSelect, disabled }: TopicChipsProps) {
  if (!topics.length) return null

  return (
    <div className="flex flex-wrap justify-center gap-2">
      {topics.map((topic) => {
        const isPest = /planthopper|midge|folder|hispa|borer/i.test(topic)
        const Icon = isPest ? Bug : Leaf
        return (
          <button
            key={topic}
            disabled={disabled}
            onClick={() => onSelect(topic)}
            className="flex items-center gap-1.5 rounded-full border border-beige bg-white px-3.5 py-2 text-sm font-medium text-forest shadow-sm transition-colors hover:border-amber hover:bg-amber-light disabled:opacity-50"
          >
            <Icon className="h-3.5 w-3.5 text-forest-muted" />
            {topic}
          </button>
        )
      })}
    </div>
  )
}
