"""Shared deterministic chat/import identity candidates; never create or merge."""

import re

from app.services.reconcile import normalize_name

_ROLE_WORDS = {
    "ال",
    "مال",
    "حق",
    "المجهز",
    "مجهز",
    "للمجهز",
    "المورد",
    "مورد",
    "للمورد",
    "الزبون",
    "زبون",
    "للزبون",
    "العميل",
    "عميل",
    "الزباين",
    "زباين",
    "الزبائن",
    "الزبايين",
    "المجهزين",
    "مجهزين",
    "للمجهزين",
    "الموردين",
    "العملاء",
}


def _words(value):
    return re.findall(r"[^\W_]+", normalize_name(value))


def candidate_ids(parties, mention, allowed):
    """Exact name, then substring, then every non-role word of the mention."""
    named = {
        key: normalize_name(name)
        for key, (name, kind) in parties.items()
        if kind in allowed
    }
    form = normalize_name(mention)
    exact = [key for key, name in named.items() if name == form]
    if exact:
        return exact
    partial = [key for key, name in named.items() if form and form in name]
    if partial:
        return partial
    kept = [word for word in _words(mention) if word not in _ROLE_WORDS]
    if not kept:
        return []
    # Word containment, so "ابو علي دفتر ب" names only "ابو علي - دفتر ب".
    return [
        key
        for key, name in named.items()
        if " ".join(kept) in " ".join(_words(name))
        or all(word in _words(name) for word in kept)
    ]


def generic_mention(mention):
    return all(token in _ROLE_WORDS for token in normalize_name(mention).split())
