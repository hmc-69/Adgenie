import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context';

export const Navbar = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const campaignMatch = location.pathname.match(/^\/campaigns\/(\d+)$/);
  const creativeStudioTarget = campaignMatch
    ? `/campaigns/${campaignMatch[1]}#creative-studio`
    : '/dashboard#campaigns';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="navbar-container">
      <div className="navbar-content">
        <Link to={isAuthenticated ? '/dashboard' : '/'} className="navbar-brand">
          <div className="brand-icon" aria-hidden="true">A</div>
          <div className="brand-text">
            <span className="brand-title">AdGenie</span>
            <span className="brand-tag">AI Marketing Intelligence</span>
          </div>
        </Link>

        <div className="navbar-actions">
          {isAuthenticated && user ? (
            <div className="user-profile-menu">
              <nav className="navbar-links" aria-label="Primary">
                <Link to="/dashboard" className={`nav-link ${location.pathname === '/dashboard' ? 'active' : ''}`}>Dashboard</Link>
                <Link to="/dashboard#campaigns" className="nav-link">Campaigns</Link>
                <Link to={creativeStudioTarget} className="nav-link">Creative Studio</Link>
              </nav>
              <div className="user-info-chip">
                <div className="user-avatar">
                  {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                </div>
                <div className="user-details">
                  <span className="user-name">{user.name}</span>
                  <span className="user-email">{user.email}</span>
                </div>
              </div>
              <button
                id="logout-btn"
                className="btn-logout"
                onClick={handleLogout}
                title="Sign out of AdGenie"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
                <span>Logout</span>
              </button>
            </div>
          ) : location.pathname === '/' ? (
            <>
              <nav className="landing-nav-links" aria-label="Landing page">
                <a href="#features">Features</a>
                <a href="#about">About</a>
              </nav>
              <div className="auth-nav-links">
                <Link to="/login" className="nav-link">Sign In</Link>
                <Link to="/register" className="btn-primary-sm">Get Started</Link>
              </div>
            </>
          ) : (
            <div className="auth-nav-links">
              <Link to="/login" className="nav-link">Sign In</Link>
              <Link to="/register" className="btn-primary-sm">Get Started</Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;
