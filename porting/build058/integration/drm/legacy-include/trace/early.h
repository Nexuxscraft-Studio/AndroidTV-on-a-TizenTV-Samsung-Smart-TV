/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * early.h - early tracing compatibility from Samsung's published Linux
 * 4.1.10 source (include/trace/early.h), copyright (C) 2014 Roman Pen.
 *
 * The original upstream kernel source archive is unchanged. This copy is
 * used ONLY to compile staged vendor DRM code against Linux 6.6.162.
 * CONFIG_EARLY_TRACING is not enabled for Build 058; no tracing backend is
 * provided or silently emulated. This is NOT drm/drm_tztv.h.
 */
#ifndef _EARLY_H
#define _EARLY_H

#ifdef CONFIG_EARLY_TRACING
extern void trace_early_message(const char *str);
#ifdef CONFIG_FIX_HWCLOCK_VA
extern void trace_early_message_fixed(const char *str);
#endif
#else
static inline void trace_early_message(const char *str) {}
#endif

#endif /* _EARLY_H */
