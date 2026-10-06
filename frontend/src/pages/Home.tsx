import { useNavigate } from 'react-router-dom'
import { Mic, Leaf, Bug, MessageCircle } from 'lucide-react'
import Card from '@/components/ui/Card'
import { useAuthStore } from '@/store/authStore'
import { useDiagnosisStore } from '@/store/diagnosisStore'
import { formatDate } from '@/lib/disease'

const MODULES = [
  {
    key: 'voice',
    icon: Mic,
    label: 'හඬ රෝගය',
    hint: 'Sinhala voice input',
    iconBg: 'bg-amber',
    to: '/voice',
    featured: true,
  },
  {
    key: 'leaf',
    icon: Leaf,
    label: 'කොළ රෝගය',
    hint: 'Upload leaf photo',
    iconBg: 'bg-green-soft',
    to: '/leaf',
  },
  {
    key: 'pest',
    icon: Bug,
    label: 'කෘමි හඳුනාගැනීම',
    hint: 'Upload pest photo',
    iconBg: 'bg-amber-dark',
    to: '/pest',
  },
  {
    key: 'chat',
    icon: MessageCircle,
    label: 'ප්‍රතිකාර උපදේශක',
    hint: 'Treatment advisory',
    iconBg: 'bg-forest',
    to: '/chat',
  },
]

export default function Home() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { voiceHistory, pestHistory } = useDiagnosisStore()

  const userHistory = user ? voiceHistory.filter((v) => v.userId === user.id).concat() : []
  const totalDiagnoses = userHistory.length + pestHistory.filter((p) => p.userId === user?.id).length
  const mostRecent = userHistory[0]

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-sinhala text-2xl font-bold text-forest">
          ආයුබෝවන්, {user?.full_name || 'ගොවියා'}!
        </h2>
        <p className="font-sinhala text-forest-muted">ඔබේ ගොයමේ රෝගය හඳුනාගැනීමට ක්‍රමයක් තෝරන්න</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {MODULES.map((mod) => (
          <button
            key={mod.key}
            onClick={() => navigate(mod.to)}
            className={`flex flex-col items-center gap-3 rounded-2xl p-5 text-center
              transition-all active:scale-95 hover:shadow-md
              ${mod.featured
                ? 'bg-amber text-white shadow-md'
                : 'bg-white text-forest shadow-sm hover:bg-beige'
              }`}
            aria-label={mod.label}
          >
            <div className={`flex h-12 w-12 items-center justify-center rounded-full
              ${mod.featured ? 'bg-white/20' : mod.iconBg}`}>
              <mod.icon className={`h-6 w-6 ${mod.featured ? 'text-white' : 'text-white'}`} />
            </div>
            <div>
              <p className={`font-sinhala text-sm font-bold
                ${mod.featured ? 'text-white' : 'text-forest'}`}>
                {mod.label}
              </p>
              <p className={`text-xs mt-0.5
                ${mod.featured ? 'text-white/70' : 'text-forest-muted'}`}>
                {mod.hint}
              </p>
            </div>
          </button>
        ))}
      </div>

      {totalDiagnoses > 0 && (
        <Card>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-forest-muted">Total Diagnoses</p>
              <p className="text-xl font-bold text-forest">{totalDiagnoses}</p>
            </div>
            <div>
              <p className="text-xs text-forest-muted">Most Recent Disease</p>
              <p className="text-xl font-bold text-forest">{mostRecent?.disease || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-forest-muted">Last Diagnosis</p>
              <p className="text-xl font-bold text-forest">{mostRecent ? formatDate(mostRecent.timestamp) : '-'}</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
