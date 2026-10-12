const dateFormat = new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'short', year: 'numeric' })

export const formatDate = (iso: string) => dateFormat.format(new Date(iso))
