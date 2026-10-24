import { Link } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { NAV_LINKS, scrollToId } from './Hero'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer-top">
          <div className="footer-brand">
            <p className="wordmark big-mark">
              <ShieldCheck size={30} strokeWidth={1.5} aria-hidden />
              <span>
                CHRONO<b>SHIELD</b>
              </span>
            </p>
            <p className="muted-p">AI-native security and governance for autonomous smart cities.</p>
          </div>
          <nav className="footer-cols" aria-label="Footer">
            <div>
              <p className="f-k">Site</p>
              {NAV_LINKS.map((l) => (
                <a
                  key={l.id}
                  href={`#${l.id}`}
                  onClick={(e) => {
                    e.preventDefault()
                    scrollToId(l.id)
                  }}
                >
                  {l.label}
                </a>
              ))}
            </div>
            <div>
              <p className="f-k">Console</p>
              <Link to="/console/overview">Overview</Link>
              <Link to="/console/policy-testing">Policy testing</Link>
              <Link to="/console/request-tester">Request tester</Link>
              <Link to="/console/audit">Audit viewer</Link>
              <Link to="/console/approvals">Approvals</Link>
            </div>
            <div>
              <p className="f-k">Research basis</p>
              <p>OWASP API Security Top 10 (2023), including Broken Object Level Authorization and Broken Function Level Authorization</p>
              <p>OWASP GenAI Security Project, Top 10 for Agentic Applications (2026)</p>
            </div>
          </nav>
        </div>
        <div className="footer-bottom">
          <p>Prototype uses synthetic data and mock services only.</p>
        </div>
      </div>
    </footer>
  )
}
