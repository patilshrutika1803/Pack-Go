const DEFAULT_CURRENCY = 'INR'

export function resolveCurrency(plan) {
  const rawCurrency = plan?.budget?.currency ?? plan?.preferences?.budget_currency ?? DEFAULT_CURRENCY

  if (typeof rawCurrency !== 'string') {
    return DEFAULT_CURRENCY
  }

  const normalized = rawCurrency.trim().toUpperCase()
  return /^[A-Z]{3}$/.test(normalized) ? normalized : DEFAULT_CURRENCY
}

export function formatCurrency(amount, currencyCode = DEFAULT_CURRENCY) {
  const safeCurrencyCode = /^[A-Z]{3}$/.test((currencyCode || '').trim().toUpperCase())
    ? currencyCode.trim().toUpperCase()
    : DEFAULT_CURRENCY

  const numericAmount = Number(amount)

  if (!Number.isFinite(numericAmount)) {
    return '—'
  }

  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: safeCurrencyCode,
      maximumFractionDigits: 0,
    }).format(numericAmount)
  } catch {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: DEFAULT_CURRENCY,
      maximumFractionDigits: 0,
    }).format(numericAmount)
  }
}
