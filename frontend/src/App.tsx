import './App.css';
import RestroomLocator from './components/RestroomLocator';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1> UMass Restroom Locator</h1>
        <p className="tagline">
          <span className="tagline-main">When you gotta go, you gotta go.</span>
          <span className="tagline-sub">Helping you navigate through our 1500 acre campus</span>
        </p>
      </header>
      <main>
        <RestroomLocator />
      </main>
      <footer className="App-footer">
        <p>© 2025 UMass Restroom Locator - Your campus convenience companion</p>
      </footer>
    </div>
  );
  
}

export default App;