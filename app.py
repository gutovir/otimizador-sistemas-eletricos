import io
import pandas as pd
import streamlit as st
from otimizador import montar_sistema, pl_unico, tabela_resultados, conferir_balancos

st.set_page_config(page_title="PL Único | Sistema Elétrico", page_icon="⚡", layout="wide")
st.title("⚡ PL Único — Planejamento de Sistemas Elétricos")
st.caption("UHE Batalha → UHE Serra do Facão | BBF Baliza e ERB Candeias")
st.info("Modelo determinístico: a trajetória de agosto a outubro é otimizada em conjunto. As afluências de Serra do Facão são locais/incrementais, sem somar novamente a água recebida de Batalha.")

with st.sidebar:
    st.header("Parâmetros da simulação")
    rotulo_cenario = st.radio("Cenário hidrológico", ["Otimista", "Pessimista"], index=0)
    cenario = 0 if rotulo_cenario == "Otimista" else 1
    carga = st.number_input("Demanda por mês (MW)", min_value=0.0, value=250.0, step=10.0)
    st.markdown("**Meses (fixos no modelo original)**")
    st.write("Agosto · Setembro · Outubro")
    st.caption("720 h por estágio, conforme notebook original. Alterar o horizonte exigiria adaptar os dados de afluência e a modelagem.")
    executar = st.button("▶ Executar otimização", type="primary", use_container_width=True)

if not executar:
    st.write("Escolha o cenário e clique em **Executar otimização**. O código matemático é o mesmo do notebook original.")
    st.stop()

sistema = montar_sistema(carga)
try:
    with st.spinner("Resolvendo o modelo de programação linear com GLPK..."):
        resultado = pl_unico(sistema, cenario=cenario, imprime=False)
        conferir_balancos(sistema, resultado)
except Exception as exc:
    st.error(f"Não foi possível resolver o modelo: {exc}")
    st.stop()

st.success("Solução ótima encontrada; balanços hídricos e atendimento à demanda conferidos.")
meses = sistema["DGer"]["Meses"]
total = resultado["DGer"]["CustoTotal"]
deficit = resultado["DGer"]["Deficit"]
cmo = resultado["DGer"]["CMO"]
a,b,c = st.columns(3)
a.metric("Custo total (R$)", f"{total:,.2f}")
b.metric("Déficit acumulado (MW por estágio)", f"{sum(deficit):,.3f}")
c.metric("CMO médio (R$/MWh)", f"{sum(cmo)/len(cmo):,.2f}")
st.caption("Os valores de déficit são MW médios por estágio; a soma é apenas um indicador entre os três estágios, não energia em MWh.")

aba1,aba2,aba3 = st.tabs(["Visão geral", "Balanço hídrico", "Tabela completa e exportação"])
with aba1:
    linhas = []
    for t, mes in enumerate(meses):
        linha = {"Mês": mes}
        for i, u in enumerate(sistema["UHE"]):
            linha[u["Nome"]] = u["Prod"] * resultado["UHE"][i]["vt"][t]
        for j, u in enumerate(sistema["UTE"]):
            linha[u["Nome"]] = resultado["UTE"][j]["gt"][t]
        linha["Déficit"] = deficit[t]
        linhas.append(linha)
    df_ger = pd.DataFrame(linhas).set_index("Mês")
    st.subheader("Atendimento à demanda por fonte (MW médios)")
    st.bar_chart(df_ger, stack=True)
    st.subheader("CMO (R$/MWh)")
    st.line_chart(pd.DataFrame({"CMO":cmo}, index=meses))
    st.subheader("Custos mensais (R$)")
    st.bar_chart(pd.DataFrame({"Custo imediato":resultado["DGer"]["CustoImediato"]}, index=meses))
with aba2:
    volumes = {}
    for i, u in enumerate(sistema["UHE"]):
        util = u["Vmax"] - u["Vmin"]
        volumes[u["Nome"]] = [(v - u["Vmin"]) / util * 100 for v in resultado["UHE"][i]["vf"]]
    st.subheader("Armazenamento final como % do volume útil")
    st.line_chart(pd.DataFrame(volumes, index=meses))
    for i, u in enumerate(sistema["UHE"]):
        st.subheader(u["Nome"])
        st.dataframe(pd.DataFrame({"Mês":meses, "Turbinado (hm³)":resultado["UHE"][i]["vt"], "Vertido (hm³)":resultado["UHE"][i]["vv"], "Volume final (hm³)":resultado["UHE"][i]["vf"]}), hide_index=True, use_container_width=True)
with aba3:
    tabela = tabela_resultados(sistema, resultado)
    st.dataframe(tabela.round(3), hide_index=True, use_container_width=True)
    st.download_button("⬇ Baixar resultados em CSV", tabela.to_csv(index=False).encode("utf-8-sig"), f"pl_unico_{rotulo_cenario.lower()}.csv", "text/csv")
    memoria = io.BytesIO()
    with pd.ExcelWriter(memoria, engine="openpyxl") as escritor:
        tabela.to_excel(escritor, sheet_name="Resultados", index=False)
    st.download_button("⬇ Baixar resultados em Excel", memoria.getvalue(), f"pl_unico_{rotulo_cenario.lower()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
