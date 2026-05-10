export default function OnboardingPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-20 text-center">
      <div className="bg-indigo-50 text-indigo-700 px-4 py-1.5 rounded-full text-sm font-bold w-fit mx-auto mb-6">
        Step 1 of 3
      </div>
      <h1 className="text-4xl font-extrabold text-slate-900 mb-6">
        Welcome to TrueBrief
      </h1>
      <p className="text-xl text-slate-600 mb-10">
        Let's get your intelligence pipeline running. What's the first thing you want to track?
      </p>
      
      <div className="relative mb-8">
        <input 
          type="text" 
          placeholder="e.g. NVIDIA Earnings, Ukraine War, iPhone 16 Leaks"
          className="w-full px-6 py-5 rounded-2xl border-2 border-slate-200 focus:border-indigo-600 focus:outline-none text-lg transition-colors shadow-sm"
        />
      </div>

      <button className="w-full bg-indigo-600 text-white py-5 rounded-2xl text-xl font-bold hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 mb-6">
        Build My First Brief
      </button>

      <button className="text-slate-400 font-medium hover:text-slate-600 transition-colors">
        Skip and go to dashboard
      </button>
    </div>
  );
}
