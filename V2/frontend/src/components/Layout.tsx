import { Outlet, Link } from 'react-router-dom';

export function Layout() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          DORA
        </Link>
        <nav>
          <Link to="/">Übersicht</Link>
          <Link to="/scenario">Neu</Link>
          <Link to="/generated">Generierte</Link>
          <Link to="/evaluate">Vergleich</Link>
          <Link to="/ns-mas">NS-MAS</Link>
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
