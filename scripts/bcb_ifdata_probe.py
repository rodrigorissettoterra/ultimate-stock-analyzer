from __future__ import annotations

import json
import unicodedata
from typing import Any

import httpx

BASE = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata"
PERIODS = (202503, 202506, 202509, 202512)
CREDIT_REPORTS = ("8", "11", "13")
LEADER_CNPJ_ROOT = "60872504"
SELECT_VALUES = (
    "TipoInstituicao,CodInst,AnoMes,NomeRelatorio,NumeroRelatorio,"
    "Grupo,Conta,NomeColuna,DescricaoColuna,Saldo"
)


def _get(client: httpx.Client, path: str, params: dict[str, object]) -> dict[str, Any]:
    response = client.get(f"{BASE}/{path}", params=params)
    print(json.dumps({"url": str(response.url), "status": response.status_code}))
    if response.status_code >= 400:
        print(json.dumps({"error_body": response.text[:1000]}, ensure_ascii=False))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("IFData response must be an object")
    return payload


def _values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("value")
    if not isinstance(rows, list):
        raise TypeError("IFData response has no value list")
    return [dict(row) for row in rows if isinstance(row, dict)]


def _cod_inst(client: httpx.Client, ano_mes: int) -> str:
    cadastro = _values(
        _get(
            client,
            "IfDataCadastro(AnoMes=@AnoMes)",
            {
                "@AnoMes": ano_mes,
                "$format": "json",
                "$select": (
                    "CodInst,Data,NomeInstituicao,CodConglomeradoPrudencial,"
                    "CnpjInstituicaoLider,Situacao"
                ),
            },
        )
    )
    candidates = [
        row
        for row in cadastro
        if row.get("Situacao") == "A"
        and row.get("CnpjInstituicaoLider") == LEADER_CNPJ_ROOT
        and row.get("CodConglomeradoPrudencial")
        and row.get("CodInst") == row.get("CodConglomeradoPrudencial")
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one Itaú prudential row for {ano_mes}, found {len(candidates)}"
        )
    return str(candidates[0]["CodInst"])


def _report_rows(
    client: httpx.Client,
    *,
    ano_mes: int,
    report: str,
    cod_inst: str,
) -> list[dict[str, Any]]:
    payload = _get(
        client,
        "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)",
        {
            "@AnoMes": ano_mes,
            "@TipoInstituicao": 1,
            "@Relatorio": f"'{report}'",
            "$format": "json",
            "$select": SELECT_VALUES,
        },
    )
    return [
        row
        for row in _values(payload)
        if str(row.get("CodInst") or "") == cod_inst
    ]


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def main() -> None:
    with httpx.Client(timeout=240.0, follow_redirects=True) as client:
        income_periodicity: dict[str, dict[str, Any]] = {}
        for ano_mes in PERIODS:
            cod_inst = _cod_inst(client, ano_mes)
            rows = _report_rows(
                client,
                ano_mes=ano_mes,
                report="4",
                cod_inst=cod_inst,
            )
            selected = {
                str(row.get("Conta")): {
                    "name": row.get("NomeColuna"),
                    "saldo": row.get("Saldo"),
                }
                for row in rows
                if str(row.get("Conta")) in {"141870", "141851", "141840", "141856", "141857", "141858", "141859"}
            }
            income_periodicity[str(ano_mes)] = {
                "cod_inst": cod_inst,
                "selected": selected,
            }
        print(
            json.dumps(
                {"income_periodicity": income_periodicity},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        cod_inst = _cod_inst(client, 202512)
        credit_quality: dict[str, Any] = {}
        keywords = ("vencid", "90", "inadimpl", "atras", "perda", "risco")
        for report in CREDIT_REPORTS:
            rows = _report_rows(
                client,
                ano_mes=202512,
                report=report,
                cod_inst=cod_inst,
            )
            interesting = [
                row
                for row in rows
                if any(
                    keyword in _plain(
                        f"{row.get('Grupo')} {row.get('NomeColuna')} {row.get('DescricaoColuna')}"
                    )
                    for keyword in keywords
                )
            ]
            credit_quality[report] = {
                "target_rows": len(rows),
                "columns": sorted({str(row.get("NomeColuna")) for row in rows}),
                "interesting_rows": interesting,
            }
        print(
            json.dumps(
                {"credit_quality": credit_quality},
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
