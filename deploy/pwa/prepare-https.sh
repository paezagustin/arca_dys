#!/bin/sh
set -eu

for attempt in $(seq 1 30); do
    if ip -o -4 addr show dev eth0 | awk '$4 == "192.168.0.80/24" { found = 1 } END { exit !found }'; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo 'eth0 todavía no tiene la dirección LAN del proxy' >&2
        exit 1
    fi
    sleep 2
done

rules=/etc/arca-dys-pwa/firewall.nft
# Reemplazar sólo esta tabla y dentro de una única transacción de nftables.
{
    if nft list table inet arca_dys_pwa >/dev/null 2>&1; then
        printf 'delete table inet arca_dys_pwa\n'
    fi
    cat "$rules"
} | nft -f -
