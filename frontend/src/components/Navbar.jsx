function Navbar({ onOpenOnboarding }) {
  return (
    <nav className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
      <div>
      <h1 className="text-3xl font-bold text-emerald-400">ArchDrift</h1>
      <p className="text-sm text-slate-400">Architectural Drift Map (Prototype)</p>
      </div>
      <button
        data-testid="onboard-button"
        onClick={onOpenOnboarding}
        className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white"
      >
        Onboard
      </button>
    </nav>
  );
}

export default Navbar;

