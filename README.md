
A U.S.-centric macro dashboard built in Python + Plotly Dash,
pulling live data. 
---

### 1. Get a free FRED API key

### 2. Install dependencies
```bash
cd macro_dashboard
pip install -r requirements.txt
```

### 3. Add your API key
Open `config.py` and set:
```python
FRED_API_KEY = "your_key_here"
```
Or set an environment variable (avoids hardcoding):
```bash
export FRED_API_KEY="your_key_here"   # Mac/Linux
set    FRED_API_KEY=your_key_here     # Windows
```

### 4. Run
```bash
python app.py
```
Open your browser at **http://127.0.0.1:8050**

---

## PROJECT STRUCTURE

```
macro_dashboard/
│
├── app.py                  ← Entry point. Run this.
├── config.py               ← All constants: API key, series IDs, colors, regimes
├── requirements.txt
│
├── data/
│   └── fetcher.py          ← FRED data pulls + disk caching
│
├── analytics/
│   └── stats.py            ← Z-scores, percentiles, regime stats
│
└── panels/
    └── rates.py            ← All charts + layout for Panel 1
```
