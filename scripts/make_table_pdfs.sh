#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
table_dir="$root_dir/results/tables"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

for name in main typing typing_rels; do
    case "$name" in
        main) table_counter=0 ;;
        typing) table_counter=1 ;;
        typing_rels) table_counter=2 ;;
    esac
    cat > "$work_dir/$name.tex" <<EOF
\documentclass{article}
\usepackage[a4paper,textwidth=12.2cm,textheight=19.3cm]{geometry}
\usepackage{amsmath}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{colortbl}
\usepackage{etoolbox}
\usepackage[hidelinks]{hyperref}
\renewcommand{\autoref}[1]{\ifstrequal{#1}{tab:main-results}{Table 1}{\ifstrequal{#1}{tab:typing-results}{Table 2}{Table 3}}}
\begin{document}
\pagestyle{empty}
\setcounter{table}{$table_counter}
\input{$table_dir/$name.tex}
\end{document}
EOF
    latexmk -pdf -interaction=nonstopmode -halt-on-error \
        -output-directory="$work_dir" "$work_dir/$name.tex" >/dev/null
    pdfcrop --margins 8 "$work_dir/$name.pdf" "$table_dir/$name.pdf" >/dev/null
done
