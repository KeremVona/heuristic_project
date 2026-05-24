# heuristic_project

## Project Setup

- ``` python3 -m venv .venv ```
- ``` source .venv/bin/activate ```
- ``` pip install mysql-connector-python ```
- ``` pip install python-dotenv ```
### VS Code Kullanımı
- Projeyi VS Code ile aç
- Ctrl + Shift + P (ya da Cmd + Shift + P).
- "Python: Select Interpreter".
- Böyle bir şey seç ('.venv': venv).
### Database Setup
- .env dosyası açıp sizin verileriniz ile doldurun. Örnek için .env.example'a bakıp görebilirsiniz.

##  Experiment ve  visualize kısmı için:
  
- To run my part, first run the experiments:

python experiments.py --pop-size 50 --n-gen 50 --max-solutions 50

Then generate the visualizations:

python visualize_results.py
