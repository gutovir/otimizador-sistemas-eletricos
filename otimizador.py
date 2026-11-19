"""Modelo de PL Único extraído do notebook original, sem mudança nas equações."""
import copy
import numpy as np
import pandas as pd

import numpy as np

horas = 720                        # 30 dias de 24 horas por estágio
k = horas * 3600 / 1_000_000      # m³/s -> hm³ por estágio: 2,592
meses = ['Agosto', 'Setembro', 'Outubro']

lista_uhe = []

# 0 = Batalha (montante). Afluências locais DIDÁTICAS em m³/s.
lista_uhe.append({
    'Nome': 'UHE Batalha',
    'Vmin': 430.049988,
    'Vmax': 1781.609985,
    'VI': 430.049988 + 0.397 * (1781.609985 - 430.049988),
    'Prod': 0.3378 / k,               # (MW por m³/s) -> (MW por hm³)
    'Engol': 147.02 * k,             # m³/s -> hm³/estágio
    'Potencia': 52.5,               # MW
    'Jusante': 1,                  # a água de Batalha chega à UHE de índice 1
    'Afl': (np.array([
        [76.0, 14.0],              # Agosto: otimista, pessimista
        [74.0, 11.0],              # Setembro
        [115.0, 8.0],              # Outubro
    ]) * k).tolist(),
})

# 1 = Serra do Facão (jusante). Afluências LOCAIS/INCREMENTAIS didáticas.
lista_uhe.append({
    'Nome': 'UHE Serra do Facão',
    'Vmin': 1752.0,
    'Vmax': 5199.0,
    'VI': 1752.0 + 0.502 * (5199.0 - 1752.0),
    'Prod': 0.6157 / k,
    'Engol': 313.0 * k,
    'Potencia': 212.58,
    'Jusante': None,
    'Afl': (np.array([
        [123.0, 22.0],             # Agosto: otimista, pessimista
        [115.0, 18.0],             # Setembro
        [183.0, 13.0],             # Outubro
    ]) * k).tolist(),
})

lista_ute = [
    {'Nome': 'BBF Baliza', 'Capac': 10.0, 'Custo': 872.76 * horas},
    {'Nome': 'ERB Candeias', 'Capac': 17.0, 'Custo': 118.93 * horas},
]

d_gerais = {
    'Meses': meses,
    'Horas': horas,
    'CDef': 8291.0 * horas,             # R$/MWh -> R$ por MW médio no estágio
    'Carga': [250.0, 250.0, 250.0],  # MW médios
    'Nr_Disc': 12,                    # parâmetro didático; PL Único não o utiliza
    'Nr_Est': 3,
    'Nr_Cen': 2,
}

sistema = {'DGer': d_gerais, 'UHE': lista_uhe, 'UTE': lista_ute}


from cvxopt.modeling import variable, solvers, op

def pl_unico(sistema, cenario=1, imprime=False):
    """PL determinístico para UHEs em cascata, seguindo a estrutura da aula.

    cenario=0: afluências otimistas; cenario=1: pessimistas.
    Afluências das UHEs a jusante devem ser LOCAIS/INCREMENTAIS.
    """
    n = sistema['DGer']['Nr_Est']
    uhes, utes = sistema['UHE'], sistema['UTE']
    if not (isinstance(cenario, int) and 0 <= cenario < sistema['DGer']['Nr_Cen']):
        raise ValueError('Use cenario=0 (otimista) ou cenario=1 (pessimista).')
    if len(sistema['DGer']['Carga']) != n:
        raise ValueError('A carga precisa ter um valor para cada estágio.')

    # Variáveis de decisão: [usina][estágio].
    vf = [variable(n, 'VF ' + u['Nome']) for u in uhes]
    vt = [variable(n, 'VT ' + u['Nome']) for u in uhes]
    vv = [variable(n, 'VV ' + u['Nome']) for u in uhes]
    gt = [variable(n, 'GT ' + u['Nome']) for u in utes]
    deficit = variable(n, 'DEF')

    # Função objetivo: coeficientes Custo e CDef já estão em R$ por MWmédio/mês.
    fob = 0
    for t in range(n):
        for j, u in enumerate(utes):
            fob += u['Custo'] * gt[j][t]
        fob += sistema['DGer']['CDef'] * deficit[t]
        for i in range(len(uhes)):
            fob += 0.01 * vv[i][t]  # pequena penalidade pelo vertimento, R$/hm³

    restricoes = []
    balancos = [[None for t in range(n)] for u in uhes]
    atendimento = []

    # Balanço hídrico, incluindo água que chega das UHEs a montante.
    # UHE de montante aponta o índice da jusante via 'Jusante'.
    for i, u in enumerate(uhes):
        for t in range(n):
            vi = float(u['VI']) if t == 0 else vf[i][t - 1]
            afl_local = float(u['Afl'][t][cenario])
            recebimento = 0
            for j, montante in enumerate(uhes):
                if montante.get('Jusante') == i:
                    recebimento += vt[j][t] + vv[j][t]
            restricao = (vf[i][t] == vi + afl_local + recebimento - vt[i][t] - vv[i][t])
            restricoes.append(restricao)
            balancos[i][t] = restricao

    # Balanço de geração: MW hidrelétricos + MW termelétricos + déficit = carga.
    for t in range(n):
        geracao = 0
        for i, u in enumerate(uhes):
            geracao += u['Prod'] * vt[i][t]
        for j in range(len(utes)):
            geracao += gt[j][t]
        geracao += deficit[t]
        restricao = (geracao == float(sistema['DGer']['Carga'][t]))
        restricoes.append(restricao)
        atendimento.append(restricao)

    # Limites físicos das UHEs, limites das UTEs e déficit não negativo.
    for t in range(n):
        for i, u in enumerate(uhes):
            restricoes += [vf[i][t] >= u['Vmin'], vf[i][t] <= u['Vmax'],
                           vt[i][t] >= 0, vt[i][t] <= u['Engol'], vv[i][t] >= 0]
            if u.get('Potencia') is not None:
                restricoes.append(u['Prod'] * vt[i][t] <= u['Potencia'])
        for j, u in enumerate(utes):
            restricoes += [gt[j][t] >= 0, gt[j][t] <= u['Capac']]
        restricoes.append(deficit[t] >= 0)

    problema = op(fob, restricoes)
    solvers.options['show_progress'] = False
    problema.solve('dense', 'glpk')
    if problema.status != 'optimal':
        raise RuntimeError(f'O PL não encontrou solução ótima: {problema.status}')

    # CMA: multiplicador do balanço hídrico; CMO: -multiplicador de AD == Carga.
    # Com GLPK pode haver pequenas diferenças numéricas nos duais (solução degenerada).
    dados_uhe = []
    for i, u in enumerate(uhes):
        dados_uhe.append({
            'Nome': u['Nome'],
            'vf': [float(vf[i][t].value()[0]) for t in range(n)],
            'vt': [float(vt[i][t].value()[0]) for t in range(n)],
            'vv': [float(vv[i][t].value()[0]) for t in range(n)],
            'cma': [float(balancos[i][t].multiplier.value[0]) for t in range(n)],
        })
    dados_ute = []
    for j, u in enumerate(utes):
        dados_ute.append({'Nome': u['Nome'],
                          'gt': [float(gt[j][t].value()[0]) for t in range(n)]})
    dados_def = [float(deficit[t].value()[0]) for t in range(n)]
    cmo = [-float(atendimento[t].multiplier.value[0]) / sistema['DGer']['Horas']
           for t in range(n)]  # R$/MWh (corrige sinal da igualdade)
    custo_imediato = [sum(utes[j]['Custo'] * dados_ute[j]['gt'][t]
                           for j in range(len(utes)))
                      + sistema['DGer']['CDef'] * dados_def[t]
                      + 0.01 * sum(dados_uhe[i]['vv'][t] for i in range(len(uhes)))
                      for t in range(n)]
    resultado = {
        'DGer': {'CustoTotal': float(fob.value()[0]), 'CMO': cmo,
                 'Deficit': dados_def, 'CustoImediato': custo_imediato,
                 'Cenario': cenario},
        'UHE': dados_uhe,
        'UTE': dados_ute,
    }
    if imprime:
        print('Custo total: R$', f"{resultado['DGer']['CustoTotal']:,.2f}")
        print('CMO (R$/MWh):', np.round(cmo, 2))
        print('Déficit (MW):', np.round(dados_def, 3))
    return resultado

def tabela_resultados(sistema, resultado):
    linhas = []
    n = sistema['DGer']['Nr_Est']
    for t in range(n):
        linha = {'Mês': sistema['DGer']['Meses'][t],
                 'Carga (MW)': sistema['DGer']['Carga'][t]}
        for i, u in enumerate(sistema['UHE']):
            linha[f'VI {u["Nome"]} (hm³)'] = u['VI'] if t == 0 else resultado['UHE'][i]['vf'][t-1]
            linha[f'AFL local {u["Nome"]} (hm³)'] = u['Afl'][t][resultado['DGer']['Cenario']]
            linha[f'VT {u["Nome"]} (hm³)'] = resultado['UHE'][i]['vt'][t]
            linha[f'VV {u["Nome"]} (hm³)'] = resultado['UHE'][i]['vv'][t]
            linha[f'VF {u["Nome"]} (hm³)'] = resultado['UHE'][i]['vf'][t]
            linha[f'Geração {u["Nome"]} (MW)'] = u['Prod'] * resultado['UHE'][i]['vt'][t]
        for j, u in enumerate(sistema['UTE']):
            linha[f'{u["Nome"]} (MW)'] = resultado['UTE'][j]['gt'][t]
        linha['Déficit (MW)'] = resultado['DGer']['Deficit'][t]
        linha['CMO (R$/MWh)'] = resultado['DGer']['CMO'][t]
        linha['Custo imediato (R$)'] = resultado['DGer']['CustoImediato'][t]
        linhas.append(linha)
    return pd.DataFrame(linhas)


def conferir_balancos(sistema, res, tolerancia=1e-5):
    n = sistema['DGer']['Nr_Est']
    for t in range(n):
        for i, u in enumerate(sistema['UHE']):
            vi = u['VI'] if t == 0 else res['UHE'][i]['vf'][t-1]
            afl_local = u['Afl'][t][res['DGer']['Cenario']]
            recebido = sum(res['UHE'][j]['vt'][t] + res['UHE'][j]['vv'][t]
                           for j, acima in enumerate(sistema['UHE']) if acima.get('Jusante') == i)
            calculado = vi + afl_local + recebido - res['UHE'][i]['vt'][t] - res['UHE'][i]['vv'][t]
            assert abs(calculado - res['UHE'][i]['vf'][t]) < tolerancia, (t, u['Nome'], calculado)
        geracao = sum(u['Prod'] * res['UHE'][i]['vt'][t] for i, u in enumerate(sistema['UHE']))
        geracao += sum(res['UTE'][j]['gt'][t] for j in range(len(sistema['UTE'])))
        geracao += res['DGer']['Deficit'][t]
        assert abs(geracao - sistema['DGer']['Carga'][t]) < tolerancia, (t, geracao)
    return True



def montar_sistema(carga_mw=250.0):
    """Cria cópia independente dos dados originais e aplica carga uniforme."""
    dados = copy.deepcopy(sistema)
    dados["DGer"]["Carga"] = [float(carga_mw)] * dados["DGer"]["Nr_Est"]
    return dados
