import { Link } from 'react-router-dom';

const featureItems = [
  {
    number: '01',
    title: 'Campaign management',
    description: 'Organize campaign goals, audiences, platforms, budgets, and status in one focused workspace.',
  },
  {
    number: '02',
    title: 'AI creative generation',
    description: 'Turn campaign context into editable image-ad briefs and structured video scripts.',
  },
  {
    number: '03',
    title: 'AI image generation',
    description: 'Create campaign-ready advertisement images from a saved creative brief and visual direction.',
  },
  {
    number: '04',
    title: 'Marketing intelligence',
    description: 'Keep audience, objective, tone, and keywords together to guide more relevant campaign creative.',
  },
];

export const LandingPage = () => (
  <div className="landing-page">
    <section className="landing-hero" id="about">
      <div className="landing-hero-copy">
        <p className="landing-eyebrow"><span /> AI Marketing Intelligence</p>
        <h1>Create smarter campaigns <em>with AI.</em></h1>
        <p className="landing-lede">
          Create, manage and enhance advertising campaigns with AI-powered creative generation and marketing intelligence.
        </p>
        <div className="landing-hero-actions">
          <Link to="/register" className="btn-primary landing-primary-cta">Get Started <span aria-hidden="true">↗</span></Link>
          <Link to="/login" className="landing-secondary-cta">Sign In <span aria-hidden="true">→</span></Link>
        </div>
        <div className="landing-proofline"><span>PLAN</span><i /> <span>CREATE</span><i /> <span>REFINE</span></div>
      </div>

      <div className="landing-preview-wrap" aria-label="AdGenie campaign workspace preview">
        <div className="preview-note">YOUR CAMPAIGN WORKSPACE</div>
        <div className="landing-product-preview">
          <div className="preview-sidebar">
            <div className="preview-brand-mark">A</div>
            <span className="preview-side-active">▦</span>
            <span>◷</span>
            <span>✳</span>
            <div className="preview-side-avatar">M</div>
          </div>
          <div className="preview-main">
            <div className="preview-topbar">
              <span>CAMPAIGN OVERVIEW</span>
              <div className="preview-user-dot">M</div>
            </div>
            <div className="preview-greeting">
              <div><small>MONDAY, OCTOBER 12</small><strong>Good morning, Maya</strong></div>
              <span className="preview-create-btn">+ New campaign</span>
            </div>
            <div className="preview-stat-row">
              <div><small>CAMPAIGNS</small><b>08</b><i>Across 4 platforms</i></div>
              <div><small>AI CREATIVES</small><b>24</b><i>Ready to refine</i></div>
              <div><small>ACTIVE</small><b>03</b><i>In market now</i></div>
            </div>
            <div className="preview-campaign-panel">
              <div className="preview-panel-heading"><b>Recent campaigns</b><small>View all ↗</small></div>
              <div className="preview-campaign-row"><span className="preview-campaign-swatch swatch-one" /><span><b>Autumn essentials</b><small>Everyday Goods · Instagram</small></span><i>Active</i></div>
              <div className="preview-campaign-row"><span className="preview-campaign-swatch swatch-two" /><span><b>Good mornings</b><small>Forma Coffee · Facebook</small></span><i className="preview-draft">Draft</i></div>
              <div className="preview-campaign-row"><span className="preview-campaign-swatch swatch-three" /><span><b>Made to wander</b><small>Northbound · TikTok</small></span><i>Active</i></div>
            </div>
          </div>
        </div>
        <div className="preview-caption"><span>01 / 03</span><span>Campaigns, creative, in one place</span></div>
      </div>
    </section>

    <section className="landing-features" id="features">
      <div className="landing-section-heading">
        <p className="landing-eyebrow">A considered way to create</p>
        <h2>From first idea to final ad.</h2>
        <p>Everything you need to shape a campaign and bring its creative to life.</p>
      </div>
      <div className="landing-feature-grid">
        {featureItems.map((feature) => (
          <article className="landing-feature" key={feature.number}>
            <span>{feature.number}</span>
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </article>
        ))}
      </div>
    </section>

    <section className="landing-final-cta">
      <div>
        <p className="landing-eyebrow">Make the next move</p>
        <h2>Ready to create your next campaign?</h2>
      </div>
      <Link to="/register" className="btn-primary landing-primary-cta">Get Started <span aria-hidden="true">↗</span></Link>
    </section>

    <footer className="landing-footer">
      <Link to="/" className="landing-footer-brand">AdGenie</Link>
      <span>AI Marketing Intelligence</span>
      <span>© {new Date().getFullYear()} AdGenie</span>
    </footer>
  </div>
);

export default LandingPage;