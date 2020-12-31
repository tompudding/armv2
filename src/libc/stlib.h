typedef int (*__compar_fn_t) (const void *, const void *);

void qsort(void  *base,
           size_t nel,
           size_t width,
           __compar_fn_t comp)
