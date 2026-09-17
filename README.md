# StockGuard — Inventory Control & Analytics

Demo funcional para una vacante de **Analista de Inventarios** en una cadena de abarrotes ficticia.

El objetivo es demostrar, con datos sintéticos, capacidades directamente relacionadas con el puesto:

- Maquila, validación y normalización de información recibida en Excel/CSV.
- Base de datos local SQLite.
- Reportes de faltantes, merma, ventas, permitidos, a cobro y entradas.
- Investigación de discrepancias por sucursal y SKU.
- Priorización automática del rol de inventarios.
- Seguimiento de incidencias.
- Exportación de reporte a Excel.

## Stack

Python · Streamlit · Pandas · SQLite · Plotly · openpyxl

Todo puede ejecutarse localmente y sin servicios de pago.

## Arranque rápido en Windows

Doble clic en `START_DEMO_WINDOWS.bat`

O con PowerShell:

```powershell
cd C:\dev\stockguard
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit abrirá normalmente `http://localhost:8501`.

## Historia de demo sugerida

1. **Ingesta de datos**: recibir un lote y detectar problemas de calidad.
2. **Dashboard**: localizar sucursales con mayor desviación.
3. **Investigación**: abrir un SKU y revisar una posible causa.
4. **Rol de inventarios**: ver la priorización de visitas.
5. **Incidencias**: registrar y dar seguimiento.
6. **Exportar reporte**: descargar el Excel con hojas operativas.

> Todos los datos son sintéticos. La aplicación no contiene información real de ninguna empresa.
