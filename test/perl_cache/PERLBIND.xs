#include "EXTERN.h"
#include "perl.h"
#include "XSUB.h"
#include <sql.h>
#include <sqlext.h>
#include <sqlucode.h>

//#include "ppport.h"
#define HV_STORE_POLICY 1

#define MAX_BUF 32767

#define MAX_CONNECTION_STRING_SIZE 256

#define MAX_TWO_FACTOR_TOKEN 2048

#define MAX_TYPE_SIZE 256

#define MAX_ID_SIZE 256

#define MAX_CLASS_NAME 2048

#define MAX_PROC_NAME 2048

#define MAX_METHOD_NAME 1024

#define MAX_PROP_NAME 1024

#define SIGNATURE_SIZE 9

#define INVALID_OBJ_WARNING(x) //if (0) warn(x)

#define INVALID_QUERY_WARNING(x) //if (0) warn(x)

#define INVALID_OBJ_WARNING1(x,y) //if (0) warn(x,y)

#define INVALID_QUERY_WARNING1(x,y) //if (0) warn(x,y)

#define DEBUG_MEM(x,y) //if (0) warn(x,y)

#define DEBUG_DESTROY(x) //if (0) warn(x)

#define DEBUG_DESTROY1(x,y) //if (0) warn(x,y)

#include <c_api.h>

#define RUN(x) run((x), __FILE__, __LINE__)

#define RUNPBIND(x) if ((retval=(x)) != 0) return retval;

#define RUNM(x) runm((x), __FILE__, __LINE__,mem_stack, p_tos)

#define RUNARG(x) runarg((x), __FILE__, __LINE__, cpp_type, var, class_name, mtd_name, argnum)

#define RUNNEWARG(x) runnewarg((x), __FILE__, __LINE__, cpp_type, class_name, mtd_name, argnum)

#define RUNARGM(x) runargm((x), __FILE__, __LINE__, cpp_type, var, class_name, mtd_name, argnum, mem_stack, *p_tos)

#define RUNNEWARGM(x) runnewargm((x), __FILE__, __LINE__, cpp_type, class_name, mtd_name, argnum, mem_stack, *p_tos)

#define PRINTARG() printarg( __FILE__, __LINE__, cpp_type, var, class_name, mtd_name, argnum)

#define MEM_STACK_SIZE 32767

#define MAXCLASSNAME 8193

#define MEM_VOID 0
#define MEM_PROP 1
#define MEM_MTD 2
#define MEM_ARG 3

typedef struct _PDATE_STRUCT {
    int year;
    int month;
    int day;
} PDATE_STRUCT;

typedef struct _PTIME_STRUCT {
    int hour;
    int minute;
    int second;
} PTIME_STRUCT;

typedef struct _PTIMESTAMP_STRUCT {
    int year;
    int month;
    int day;
    int hour;
    int minute;
    int second;
    int fraction;
} PTIMESTAMP_STRUCT;

typedef struct _Mem_Ptr {
    void *ptr;
    int type;
} Mem_Ptr;

typedef struct {
    long oref;
    h_database db;
    wchar_t cl_name[MAXCLASSNAME];
} mycbind_obj;

typedef struct _my_var {
    mycbind_obj v;
    char *origin;
} my_var;

typedef struct _Object {
    my_var *_object;
    SV *_database; // should not be RV must be SV
    int _objid;
    int _active;
    int *database_being_destroyed;
} Object;

typedef struct _ObjectNode {
    struct _ObjectNode *prev;
    struct _ObjectNode *next;
    Object *object;
} ObjectNode;

typedef struct _Query {
    h_query _query;
    int _queryid;
    int _active;
    SV *_database;  // should not be RV must be SV
    int *database_being_destroyed;
} Query;

typedef struct _QueryNode {
    struct _QueryNode *prev;
    struct _QueryNode *next;
    Query *query;
} QueryNode;

typedef struct _Database {
    char signature[SIGNATURE_SIZE];
    int *database_being_destroyed;
    ObjectNode *object_list;
    QueryNode *query_list;
    h_database _database;
    SV *_connection;
} Database;

typedef struct _Status {
    char signature[SIGNATURE_SIZE];
    int code;
    int status_size;
    int size;
    char msg[MAX_BUF];
    char buf[MAX_BUF];
} Status;

typedef struct {
    h_prop_def prop_def;
    short cpp_type;
    const wchar_t* cache_type;
    const wchar_t* name;
} pbind_prop_def;

typedef struct {
    h_mtd_def mtd_def;
    bool_t is_func;
    short cpp_type;
    const wchar_t* cache_type;

    bool_t is_cls_mtd;

    int num_args;
    void* args_info;
    const wchar_t *name;
} pbind_mtd_def;

typedef struct {
    h_arg_def arg_def;
    short cpp_type;
    const wchar_t* cache_type;
    const wchar_t* name;

    bool_t is_by_ref;
    bool_t is_default;
    const char* def_val;
    long def_val_size;
} pbind_arg_def;

void remove_object_from_database(SV *dbhashsv, Object *object);
void remove_query_from_database(SV *dbhashsv, Query *query);
SV *Binary2SV(char *buffer, int len);
char * SV2Binary(SV *sv, int *plen);
int parsedecimal(SV *svin, SV *refdecimal);
int parsetime(SV *svin, SV *reftime);
int parsedate(SV *svin, SV *refdate);
int parsetimestamp(SV *svin, SV *reftimestamp);
SV *objectrv(my_var *var);
SV *queryrv(h_query query);
h_connection get_conn(SV *sv);
Database *get_database(SV *sv);
h_database get_db(SV *sv);
my_var *get_var(SV *sv);
Status *get_status(SV *sv);
Object *get_object(SV *sv);
Query *get_query(SV *sv);
h_query get_query_handle(SV *sv);
SV *connhashrv(h_connection con);
SV *databasehashrv(h_database res, SV* con);
void setdb(SV *sv, SV* dbhashsv);
void setqdb(SV *rquery, SV* dbhashrv);
SV *make_status(int code, wchar_t *msg, int size,int cpp_type, char *class_name, char *mtd_name, int argnum, Mem_Ptr mem_stack[], int *p_tos, int is_return);
SV *statusrv(int code, char* buf, int size, char* msg, int status_size);
void printw(char*msg,wchar_t *p);
SV * get_database_sv(SV *sv);
void setobjid(SV *sv, int objid);
int getobjid(SV *sv);
void setobjactive(SV *sv, int active);
int getobjactive(SV *sv);
void destroy_obj(Object *obj);
void destroy_query(Query *obj);
int get_size_utf8_to_uni(char *utf8str, int len);
int get_size_uni_to_utf8(wchar_t *uni_str, int unilen);
void get_decimal(SV *decimal, __int64 *significand, schr *exponent);
SV *set_decimal(__int64 significand, schr exponent);

int pbind_get_prop_def(h_class_def cl_def,
                       const wchar_t* name,
                       pbind_prop_def *res,
                       Mem_Ptr mem_stack[],
                       int *p_tos);

int pbind_get_dyn_prop_def(h_database db,
                           h_objref oref,
                           const wchar_t* name,
                           pbind_prop_def *res,
                           Mem_Ptr mem_stack[],
                           int *p_tos);

int pbind_get_mtd_def(h_class_def cl_def,
                      const wchar_t* name,
                      pbind_mtd_def *res,
                      Mem_Ptr mem_stack[],
                      int *p_tos);

int pbind_get_dyn_mtd_def(h_database db,
                          h_objref oref,
                          const wchar_t* name,
                          pbind_mtd_def *res,
                          Mem_Ptr mem_stack[],
                          int *p_tos);


int pbind_mtd_rewind_args(pbind_mtd_def *res);
int pbind_mtd_arg_get(pbind_mtd_def *mtd_def, pbind_arg_def *arg_def);
int pbind_mtd_arg_next(pbind_mtd_def *mtd_def);

int pbind_get_next_prop_def(h_class_def h_cl_def, pbind_prop_def *prop_def, bool_t *p_at_end);
int pbind_get_next_mtd_def(h_class_def h_cl_def, pbind_mtd_def *mtd_def, bool_t *p_at_end);

// date, time, timestamp functions
static int pbind_set_next_arg_as_time(h_database h_db, const PTIME_STRUCT* val, bool_t by_ref);
static int pbind_set_next_arg_as_date(h_database h_db, const PDATE_STRUCT* val, bool_t by_ref);
static int pbind_set_next_arg_as_mv_date(h_database h_db, const PDATE_STRUCT* val, bool_t by_ref);
static int pbind_set_next_arg_as_timestamp(h_database h_db, const PTIMESTAMP_STRUCT* val, bool_t by_ref);
static int pbind_get_arg_as_date(h_database h_db, int idx, PDATE_STRUCT* val, bool_t *p_is_null);
static int pbind_get_arg_as_time(h_database h_db, int idx, PTIME_STRUCT* val, bool_t *p_is_null);
static int pbind_get_arg_as_timestamp(h_database h_db, int idx, PTIMESTAMP_STRUCT* val, bool_t *p_is_null);
static int pbind_query_get_date_data(h_query _query, PDATE_STRUCT* res, bool_t *p_isnull);
static int pbind_query_get_time_data(h_query _query, PTIME_STRUCT* res, bool_t *p_isnull);
static int pbind_query_get_timestamp_data(h_query _query, PTIMESTAMP_STRUCT* res, bool_t *p_isnull);
static int pbind_query_set_date_par(h_query _query, int idx, const PDATE_STRUCT* val);
static int pbind_query_set_time_par(h_query _query, int idx, const PTIME_STRUCT* val);
static int pbind_query_set_timestamp_par(h_query _query, int idx, const PTIMESTAMP_STRUCT* val);

static int objid=0;
static int queryid=0;

// C binding APIs moved here
int mycbind_get_obj(mycbind_obj* cobj, int* oref, h_database* h_db, const wchar_t **cl_name)
{
    *oref = cobj->oref;
    *h_db = cobj->db;
    *cl_name = cobj->cl_name;
    return 0;
}

int mycbind_obj_init(mycbind_obj *cobj) 
{
    cobj->oref = 0;
    return 0;
}

int mycbind_object_clear(mycbind_obj *cobj)
{
    cbind_object_release(cobj->db, cobj->oref);
    return 0;
}

int mycbind_set_obj(mycbind_obj* cobj, int oref, h_database h_db, const_name_t cl_name)
{
    cobj->db = h_db;
    cobj->oref = oref;
    wcsncpy(cobj->cl_name, cl_name, MAXCLASSNAME);
    return 0;

}

int cbind_get_cl_name(mycbind_obj* cobj, const wchar_t** res)
{
    *res = cobj->cl_name;
    return 0;
}

// end of C binding APIS moved here

int run(int err, char *file, int line) {
    if (err != 0) {
        warn("err=%d",err);
        warn("message=%s",cbind_get_last_err_msg());
        Perl_croak(aTHX_ "file=%s line=%d err=%d message=%s\n", file, line, err, cbind_get_last_err_msg());
                                   }
    return err;
}

void free_mem_stack(Mem_Ptr mem_stack[], int tos, char *file, int line)
{
    int i;
    for (i=0; i < tos; i++) {
        //warn("freeing mem_stack ptr=%x", mem_stack[i].ptr);
        switch (mem_stack[i].type) {
            case MEM_VOID:
                Safefree(mem_stack[i].ptr);
                break;
            case MEM_MTD:
                cbind_free_mtd_def(mem_stack[i].ptr);
                break;
            case MEM_PROP:
                cbind_free_prop_def(mem_stack[i].ptr);
                break;
            case MEM_ARG:
                cbind_free_arg_def(mem_stack[i].ptr);
                break;
            default:
                Perl_croak(aTHX_ "file=%s line=%d message=%s\n", file, line, "freeing pointer with invalid type");
        }
    }

}

int runm(int err, char *file, int line, Mem_Ptr mem_stack[], int *p_tos) {
    if (err != 0) {
        // free all mem on mem_stack
        free_mem_stack(mem_stack, *p_tos, file, line);
    }
    if (err != 0) {
        warn("err=%d",err);
        warn("message=%s",cbind_get_last_err_msg());
        Perl_croak(aTHX_ "file=%s line=%d err=%d message=%s\n", file, line, err, cbind_get_last_err_msg());
    }
    return err;
}

int runnewarg(int err, char *file, int line, int cpp_type, char *class_name, char *mtd_name, int argnum) {
	if (err != 0) {
		warn("err=%d",err);
		warn("message=%s",cbind_get_last_err_msg());
		Perl_croak(aTHX_ "file=%s line=%d err=%d message=%s cpp_type=%d class_name=%s mtd_name=%s argnum=%d\n", file, line, err, cbind_get_last_err_msg(), cpp_type,  class_name, mtd_name, argnum);
	}
	return err;
}

int runnewargm(int err, char *file, int line, int cpp_type, char *class_name, char *mtd_name, int argnum, Mem_Ptr mem_stack[], int tos) {
    if (err != 0) {
        free_mem_stack(mem_stack, tos, file, line);
    }
	if (err != 0) {
		warn("err=%d",err);
		warn("message=%s",cbind_get_last_err_msg());
		Perl_croak(aTHX_ "file=%s line=%d err=%d message=%s cpp_type=%d class_name=%s mtd_name=%s argnum=%d\n", file, line, err, cbind_get_last_err_msg(), cpp_type,  class_name, mtd_name, argnum);
	}
	return err;
}

void push_mem_stack(Mem_Ptr mem_stack[], int *p_tos, void *ptr, int mem_type)
{
    if (*p_tos >= MEM_STACK_SIZE) Perl_croak(aTHX_ "Out of stack to record memory");
    mem_stack[*p_tos].ptr = ptr;
    mem_stack[*p_tos].type = mem_type;
    ++*p_tos;
}

void pop_mem_stack(int *p_tos)
{
    if (*p_tos <= 0) Perl_croak(aTHX_ "Stack underflow on stack to record memory");
    --*p_tos;
}

void printw(char *msg, wchar_t *p) {
    printf("%s",msg); wprintf(L"%s\n",p);
}

int get_size_utf8_to_uni(char *utf8str, int len) {

    return len; // returned unisize is always 0, due to bug in cbind_utf8_to_uni
    /*
    int unisize;
    cbind_utf8_to_uni(utf8str, len, NULL, 0, &unisize);
    if (len > 0 && unisize==0) Perl_croak(aTHX_ "file=%s line=%d, Bad UTF8 string \"%s\"\n", __FILE__, __LINE__,utf8str);
    return unisize; // returned unisize is always 0, due to bug in cbind_utf8_to_uni
    */
}

int get_size_uni_to_utf8(wchar_t *uni_str, int unilen) {
    /*
    int utf8size;

    cbind_uni_to_utf8(uni_str, unilen, NULL, 0, &utf8size);
    if (unilen != 0 && utf8size == 0) Perl_croak(aTHX_ "file=%s line=%d, Bad UTF8 string \"%ls\"\n", __FILE__, __LINE__,uni_str);
    return utf8size;
    */
    return 3 * unilen; // problem with cbind_uni_to_utf8

}

static char *strRev(char *s);

char *i64toa(__int64 n, char *s, int b) {
	static char digits[] = "0123456789abcdefghijklmnopqrstuvwxyz";
	int i=0;
	__int64 sign;

	if (n == (-9223372036854775807LL - 1) && b == 10) {
		strcpy(s,"-9223372036854775808");
		return s;
	}
	
	if ((sign = n) < 0)
		n = -n;

	do {
		s[i++] = digits[n % b];
	} while ((n /= b) > 0);

	if (sign < 0)
		s[i++] = '-';
	s[i] = '\0';

	return strRev(s);
}

char* strRev(char* szT)
{
    STRLEN i, t, k, j;
    char ch;
    
    if ( !szT )                 // handle null passed strings.
        return "";
    i = strlen(szT);
    t = !(i%2)? 1 : 0;      // check the length of the string .
    for(j = i-1 , k = 0 ; j > (i/2 -t) ; j-- )
    {
        ch  = szT[j];
        szT[j]   = szT[k];
        szT[k++] = ch;
    }
    return szT;
}
    
void setSVasArg(SV *sv, h_database h_db, int cpp_type, bool_t by_ref, const_name_t cl_name, char *class_name, char *mtd_name, int argnum, Mem_Ptr mem_stack[], int *p_tos) {
	if (!SvOK(sv)) {  // undef is null
		RUNNEWARG(cbind_set_next_arg_as_null(h_db,  cpp_type, by_ref));
		return;
	}
	switch (cpp_type) {
		case CBIND_VOID:
			break;
		case CBIND_OBJ_ID:
		{
			my_var *invar;
            h_database db;
            const wchar_t *p_cl_name;
			int oref;
			invar = get_var(sv);
			RUNNEWARG(mycbind_get_obj(&invar->v, &oref, &db, &p_cl_name));
			RUNNEWARG(cbind_set_next_arg_as_obj(h_db, oref, p_cl_name, by_ref));
			break;
		}
		case CBIND_INT_ID:
		{
	    //int i = (int)SvIV(sv);
		//warn("i=%d\n",i);
			
			RUNNEWARG(cbind_set_next_arg_as_int(h_db, (__int64)SvIV(sv), by_ref));
			break;
		}
		case CBIND_DOUBLE_ID:
			RUNNEWARG(cbind_set_next_arg_as_double(h_db, (double)SvNV(sv), by_ref));
            break;
            /* This one was missing: q&d fix, added by Frederic */
        case CBIND_DECIMAL_ID:
        {
            __int64 significand;
            schr exponent;
#if 0
            __int64 ival = (__int64)SvNV(sv);
            STRLEN len;
            schr exp = 0;
            char *asString = SvPV(sv, len);
            char *p = strchr(SvPV(sv, len), '.');
            warn("asString=%s\n",asString);
            if (p != NULL) {
                p++;
                while (*p) {
                    ival = ival * 10 + (*p - '0');
                    exp--;
                    p++;
                }
            }
#endif
            // 05-12-11
            if (sv_isobject(sv) && sv_derived_from(sv, "Intersys::PERLBIND::Decimal")) {
                get_decimal(sv, &significand, &exponent);
                
            } else {
#if 0                
                SV *rv;
                SV *svdecimal;
                int rc;
                svdecimal = newHV(); // svdate now points to ref
                rv = newRV_noinc(svdecimal);
                rc = parsedecimal(sv,rv); // we ignore rc, always successful?
                get_decimal(rv, &significand, &exponent);
#endif                
                Perl_croak(aTHX_ "expecting an Intersys::PERLBIND::Decimal"); 
            }
            RUNNEWARG(cbind_set_next_arg_as_decimal(h_db, significand, exponent, by_ref));
            break;
        }
        /* end addition by Frederic */        
		case CBIND_BINARY_ID:
		{
			int len;
			char *buf = SV2Binary(sv, &len);

			RUNNEWARG(cbind_set_next_arg_as_bin(h_db, buf, len, by_ref));
			Safefree(buf);
			break;
		}
		case CBIND_STRING_ID:
		{
            STRLEN len;
            wchar_t unistr[MAX_BUF];
            int unisize;
            wchar_t *p_unistr;
            char *p_utf8str;
            int uni_type;

            sv_utf8_upgrade(sv);
            p_utf8str = SvPV(sv, len);
            //for (i=0; i < len; i++) warn("p_utf8str[%d]=%x\n",i,p_utf8str[i]);
			unisize = get_size_utf8_to_uni(p_utf8str, (int)len);

			unisize+=sizeof(wchar_t);
            if (unisize < sizeof(unistr)) {
                p_unistr = unistr;
            } else {
                Newx( p_unistr, unisize, wchar_t);
                push_mem_stack(mem_stack, p_tos, p_unistr, MEM_VOID);
            }
            cbind_utf8_to_uni(p_utf8str, (int)len, p_unistr, unisize, &unisize);

			uni_type = CPP_UNICODE;
            //warn("var.cpp_type=%d var.obj.oref=%d\n", var->cpp_type, var->obj.oref);
            RUNNEWARG(cbind_set_next_arg_as_str(h_db, (char*)p_unistr, sizeof(wchar_t) * unisize, uni_type, by_ref));
            if (unisize >= sizeof(unistr)) {
                Safefree(p_unistr);
                pop_mem_stack(p_tos);
            }
            
			break;
		}
		case CBIND_STATUS_ID:
        {
            Status *status = get_status(sv);
            char *buf = status->buf;
            byte_size_t size = status->size;
            RUNNEWARG(cbind_set_next_arg_as_bin(h_db, buf, size, by_ref));

			break;
		}
		case CBIND_TIME_ID:
		{
			IV tmp;
			PTIME_STRUCT *in;
			if (sv_isobject(sv) && sv_derived_from(sv, "PTIME_STRUCTPtr")) {
				tmp = SvIV((SV*)SvRV(sv));
				in = INT2PTR(PTIME_STRUCT *, tmp);
				RUNNEWARG(pbind_set_next_arg_as_time(h_db, in, by_ref));
			} else {
				PTIME_STRUCT time_struct;
				SV *svtime;
				SV *rv;
				int rc;
				svtime = newSV(0); // svdate now points to ref
				rv = newRV_noinc(svtime);
				sv_setref_pv(rv, "PTIME_STRUCTPtr", &time_struct);
				rc = parsetime(sv,rv);
				RUNNEWARG(pbind_set_next_arg_as_time(h_db, &time_struct, by_ref));
				if (rc != 0) Perl_croak(aTHX_ "expecting a valid time or a PTIME_STRUCTPtr");

			}
			break;
		}
		case CBIND_DATE_ID:
		{
			IV tmp;
			PDATE_STRUCT *in;
			if (sv_isobject(sv) && sv_derived_from(sv, "PDATE_STRUCTPtr")) {
				tmp = SvIV((SV*)SvRV(sv));
				in = INT2PTR(PDATE_STRUCT *, tmp);
				RUNNEWARG(pbind_set_next_arg_as_date(h_db, in, by_ref));
			} else {
				PDATE_STRUCT date_struct;
				SV *svdate;
				SV *rv;
				int rc;
				svdate = newSV(0); // svdate now points to ref
				rv = newRV_noinc(svdate);
				sv_setref_pv(rv, "PDATE_STRUCTPtr", &date_struct);
				rc = parsedate(sv,rv);
				RUNNEWARG(pbind_set_next_arg_as_date(h_db, &date_struct, by_ref));
				if (rc != 0) Perl_croak(aTHX_ "expecting a valid date or a PDATE_STRUCTPtr");

			}
			break;
		}
		case CBIND_MV_DATE_ID:
		{
			IV tmp;
			PDATE_STRUCT *in;
			if (sv_isobject(sv) && sv_derived_from(sv, "PDATE_STRUCTPtr")) {
				tmp = SvIV((SV*)SvRV(sv));
				in = INT2PTR(PDATE_STRUCT *, tmp);
				RUNNEWARG(pbind_set_next_arg_as_mv_date(h_db, in, by_ref));
			} else {
				PDATE_STRUCT date_struct;
				SV *svdate;
				SV *rv;
				int rc;
				svdate = newSV(0); // svdate now points to ref
				rv = newRV_noinc(svdate);
				sv_setref_pv(rv, "PDATE_STRUCTPtr", &date_struct);
				rc = parsedate(sv,rv);
				RUNNEWARG(pbind_set_next_arg_as_mv_date(h_db, &date_struct, by_ref));
				if (rc != 0) Perl_croak(aTHX_ "expecting a valid date or a PDATE_STRUCTPtr");

			}
			break;
		}
		case CBIND_TIMESTAMP_ID:
		{
			IV tmp;
			PTIMESTAMP_STRUCT *in;
			if (sv_isobject(sv) && sv_derived_from(sv, "PTIMESTAMP_STRUCTPtr")) {
				tmp = SvIV((SV*)SvRV(sv));
				in = INT2PTR(PTIMESTAMP_STRUCT *, tmp);
				RUNNEWARG(pbind_set_next_arg_as_timestamp(h_db, in, by_ref));
			} else {
				PTIMESTAMP_STRUCT timestamp_struct;
				SV *svtimestamp;
				int rc;
				SV *rv;
				svtimestamp = newSV(0); // svdate now points to ref
				rv = newRV_noinc(svtimestamp);
				sv_setref_pv(rv, "PTIMESTAMP_STRUCTPtr", &timestamp_struct);
				rc = parsetimestamp(sv,rv);
				RUNNEWARG(pbind_set_next_arg_as_timestamp(h_db, &timestamp_struct, by_ref));
				if (rc != 0) Perl_croak(aTHX_ "expecting a valid timestamp or a PTIMESTAMP_STRUCTPtr");
			}
			break;
		}
		case CBIND_BOOL_ID:
		{
			RUNNEWARG(cbind_set_next_arg_as_bool(h_db, (bool_t)SvIV(sv), by_ref));
			break;
		}
		case CBIND_CURRENCY_ID:
		{
			RUNNEWARG(cbind_set_next_arg_as_cy(h_db, (double)SvNV(sv), by_ref));            
			break;
		}
		case CBIND_DLIST_ID:
		{
			AV *av;
			I32 n;
			int i;
			SV **pelem;
			SV *elem;
			char buf[MAX_BUF];
			int elem_size;
			char *p;

			av = (AV*)SvRV(sv); // get the array from the array reference
			n = av_len(av)+1;
	    //warn("n=%d\n",n);
			p = buf;
			for (i=0; i < n && p < buf + sizeof(buf); i++) {
				pelem = av_fetch(av, i, 0);
				if (pelem != NULL && *pelem != NULL) {
                    elem = *pelem;
                    if (elem == &PL_sv_undef) {
                        RUNNEWARG(cbind_dlist_put_null_elem(p, (int)(buf + sizeof(buf) -p), &elem_size));                                                
                    }
					else if (!SvOK(elem)) {
                        RUNNEWARG(cbind_dlist_put_null_elem(p, (int)( buf + sizeof(buf) -p), &elem_size));                        
					}
					else if SvIOK(elem) { // process integer
                        //RUNNEWARG(cbind_dlist_put_int_elem(p, buf + sizeof(buf) -p, (int)SvIV(elem), &elem_size));
						int val;

                        val = (int)SvIV(elem);
                        RUNNEWARG(cbind_dlist_put_int_elem(p, (int)(buf + sizeof(buf) -p),val,&elem_size));

					} else if (SvNOK(elem)) { // process double
                        //RUNNEWARG(cbind_dlist_put_double_elem(p, buf
                        //+ sizeof(buf) -p, (double)SvNV(elem), &elem_size));
                        double val;

                        val = SvNV(elem);
                        RUNNEWARG(cbind_dlist_put_double_elem(p, (int) (buf + sizeof(buf) -p),val,&elem_size));                        
                        

					} else if (SvPOK(elem)) { // process string
                        char *str;
                        STRLEN len;
                        wchar_t unistr[MAX_BUF];
                        int unisize;
                        wchar_t *p_unistr;
                        
                        sv_utf8_upgrade(elem);
                        str = SvPV(elem, len);

                        unisize = get_size_utf8_to_uni(str, (int)len);
						unisize++;
                        if (unisize < sizeof(unistr)) {
                            p_unistr = unistr;
                        } else {
                            Newx( p_unistr, unisize, wchar_t);
                            push_mem_stack(mem_stack, p_tos, p_unistr, MEM_VOID);
                        }
                        cbind_utf8_to_uni(str, (int)len, p_unistr, unisize, &unisize);
                        RUNNEWARG(cbind_dlist_put_str_elem(p, (int)(buf + sizeof(buf) -p),1,(char*)p_unistr,unisize*sizeof(wchar_t), &elem_size));

					} else {
						Perl_croak(aTHX_ "unknown processing element processing array representing %%List, type = %d class_name=%s method name = %s argnum=%d", cpp_type, class_name, mtd_name, argnum);
					}
					p += elem_size;
				} else {
					Perl_croak(aTHX_ "array element NULL in array representing %%List, type = %d class_name=%s method name = %s argnum=%d", cpp_type, class_name, mtd_name, argnum);

				}

			} // end for 
	    // set buf we've set
			RUNNEWARG(cbind_set_next_arg_as_dlist(h_db, buf,(byte_size_t) (p - buf), by_ref));
			break;
		}
		default:
			Perl_croak(aTHX_ "unknown type for argument, type = %d class_name=%s method name = %s argnum=%d", cpp_type, class_name, mtd_name, argnum);



	}
}

void getArgAsSV(SV *sv, h_database h_db, SV *dbhashsv, bool_t *is_null, int cpp_type, char *class_name, char *mtd_name, int argnum, Mem_Ptr mem_stack[], int *p_tos, int is_return) {

    bool_t isnull;
    RUNNEWARGM(cbind_get_is_null(h_db, argnum, is_null));
    if (*is_null != 0) {
        sv_setsv(sv, &PL_sv_undef);
        return;
    }
    
    switch (cpp_type) {
        case CBIND_VOID:
            break;
        case CBIND_OBJ_ID:
        {
            my_var *ret;
            int oref;
            SV *object_rv;
            const wchar_t * cl_name;
            char_size_t len;
	    
            Newx( ret, 1, my_var);
            mycbind_obj_init(&ret->v);
            push_mem_stack(mem_stack, p_tos, ret, MEM_VOID);
            DEBUG_MEM("MEMX allocated my_var=%x in getArgAsSv",ret);
            RUNNEWARGM(cbind_get_arg_as_obj(h_db, argnum, &oref, &cl_name, &len, &isnull));
            //warn("oref=%d\n", oref);
            RUNNEWARGM(mycbind_set_obj(&ret->v, oref, h_db, cl_name));
            ret->origin = "copyVarToSv";
            object_rv = objectrv(ret);
            pop_mem_stack(p_tos);
            setdb(object_rv, dbhashsv);
            sv_setsv(sv, object_rv); // also frees what used to be in sv
            // !!! next line important, without this when
            // $obj->get($property) returns an object, its refcnt is 2
            // not 1!!!!
            SvREFCNT_dec(object_rv); 
            break;
        }                   
        case CBIND_INT_ID:
        {
            __int64 val64;
			int val;
			char digits[22];
	    
			RUNNEWARGM(cbind_get_arg_as_int(h_db, argnum,  &val64, &isnull));
			if (val64 >= INT_MIN && val64 <= INT_MAX) {
                val = (int)val64;
				sv_setiv(sv, val);
			} else {
                i64toa(val64, digits, 10);
				sv_setpv(sv, digits);
			}
            break;
        }
        case CBIND_DOUBLE_ID:
        {
            double val;
            RUNNEWARGM(cbind_get_arg_as_double(h_db, argnum, &val, &isnull));
            sv_setnv(sv, val);
            
            break;
        }
        /* This one was missing: q&d fix, added by Frederic */
        case CBIND_DECIMAL_ID:
        {
            __int64 significand;
            int dflag = 0;
            schr exponent;
            SV *decimal_rv;

            RUNNEWARGM(cbind_get_arg_as_decimal(h_db, argnum, 
                                                &significand, &exponent,
                                                &isnull));
#if 0            
            while (exp > 0) {
                val *= 10;
                exp--;
            }
            sprintf(buf, "%ld", val);
            p = strchr(buf, '\0');
            dflag = (exp < 0);
            while (exp < 0) {
                *(p+1) = *p;
                p--;
                exp++;
            }
            if (dflag) {
                *(p+1) = *p;
                *p = '.';
            }
            sv_setpv(sv, buf);
#endif
            decimal_rv = set_decimal(significand, exponent);
            sv_setsv(sv, decimal_rv); // also frees what used to be in sv
            // !!! next line important, without this when
            // $obj->get($property) returns a decimal, its refcnt is 2
            // not 1!!!!
            SvREFCNT_dec(decimal_rv); 
            
            break;
        }
        /* end addition */
        
        case CBIND_BINARY_ID:
        {
            SV *svtmp;
            char buf[MAX_BUF];
            byte_size_t size;
            char *p_buf;

            RUNNEWARGM(cbind_get_arg_as_bin(h_db, argnum, NULL, 0,&size, &isnull));	    
            if (size <= sizeof(buf)) {
                p_buf = buf;
            } else {
                Newx( p_buf, size, char);
                push_mem_stack(mem_stack, p_tos, p_buf, MEM_VOID);

            }
	    
            RUNNEWARGM(cbind_get_arg_as_bin(h_db, argnum, p_buf, size, &size, &isnull));
            svtmp = Binary2SV(p_buf, size);
            sv_setsv(sv, svtmp);
            SvREFCNT_dec(svtmp);
            if (size > sizeof(buf)) {
                Safefree(p_buf);
                pop_mem_stack(p_tos);
            }
	    
            break;
        }
        case CBIND_STRING_ID:
        {
            char unistr[MAX_BUF];
            char utf8str[MAX_BUF];
            byte_size_t unisize;
            int utf8size;
            char *p_utf8str;
            char *p_unistr;

            RUNNEWARGM(cbind_get_arg_as_str(h_db, argnum, unistr, 0, CPP_UNICODE, &unisize, &isnull));

            if (unisize <= sizeof(unistr))
                p_unistr = unistr;
            else {
                Newx( p_unistr, unisize, char);
                push_mem_stack(mem_stack, p_tos, p_unistr, MEM_VOID);

            }
            RUNNEWARGM(cbind_get_arg_as_str(h_db, argnum, p_unistr, unisize, CPP_UNICODE, &unisize, &isnull));
            utf8size = get_size_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t));
            if (utf8size <= sizeof(utf8str))
                p_utf8str = utf8str;
            else {
                Newx( p_utf8str, utf8size, char);
                push_mem_stack(mem_stack, p_tos, p_utf8str, MEM_VOID);

            }

            RUNNEWARGM(cbind_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t), p_utf8str, utf8size, &utf8size));
            sv_setpvn(sv, p_utf8str, utf8size);
            SvUTF8_on(sv);
            if (unisize > sizeof(unistr)) {
                Safefree(p_unistr);
                pop_mem_stack(p_tos);
            }
            if (utf8size > sizeof(utf8str)) {
                Safefree(p_utf8str);
                pop_mem_stack(p_tos);
            }

            break;
        }
        case CBIND_STATUS_ID:
        {
            int code;
            SV *status_sv;
            char unistr[MAX_BUF];
            byte_size_t unisize;
            char *p_unistr;
            char buf[MAX_BUF];
            char *p_buf;
            byte_size_t bufsize;
            char utf8str[MAX_BUF];
            int utf8size;
            char *p_utf8str;

            RUNNEWARGM(cbind_get_arg_as_status(h_db, argnum, &code, NULL, 0, CPP_UNICODE, &unisize, &isnull));
            if (unisize <= sizeof(unistr)) {
                p_unistr = unistr;
            } else {
                Newx( p_unistr, unisize, char);
                push_mem_stack(mem_stack, p_tos, p_unistr, MEM_VOID);

            }
            RUNNEWARGM(cbind_get_arg_as_status(h_db, argnum, &code, p_unistr, unisize, CPP_UNICODE, &unisize, &isnull));	    
            p_unistr[unisize] = 0;


            utf8size = get_size_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t));
            if (utf8size <= sizeof(utf8str))
                p_utf8str = utf8str;
            else {
                Newx( p_utf8str, utf8size, char);
                push_mem_stack(mem_stack, p_tos, p_utf8str,MEM_VOID);

            }
           if (unisize/sizeof(wchar_t) != 0) {
               RUNNEWARGM(cbind_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t), p_utf8str, utf8size, &utf8size));
           } else {
               utf8size = 0;
           }
           p_utf8str[utf8size] = 0;

           //status_sv = make_status(code, (wchar_t*)p_unistr, unisize, cpp_type, class_name, mtd_name, argnum, mem_stack, p_tos,is_return);
           RUNNEWARGM(cbind_get_arg_as_bin(h_db, argnum, NULL, 0, &bufsize, &isnull));
           if (bufsize <= sizeof(buf)) {
               p_buf = buf;
           } else {
               Newx( p_buf, bufsize, char);
               push_mem_stack(mem_stack, p_tos, p_buf, MEM_VOID);
           }
           RUNNEWARGM(cbind_get_arg_as_bin(h_db, argnum, p_buf, bufsize, &bufsize, &isnull));
           status_sv = statusrv(code, buf, bufsize, p_utf8str, utf8size);
           sv_setsv(sv, status_sv);
           SvREFCNT_dec(status_sv);
           if (unisize > sizeof(unistr)) {
               Safefree(p_unistr);
               pop_mem_stack(p_tos);
           }
           if (utf8size > sizeof(utf8str)) {
               Safefree(p_utf8str);
               pop_mem_stack(p_tos);
           }

           if (bufsize > sizeof(buf)) {
               Safefree(p_buf);
               pop_mem_stack(p_tos);
           }

           break;

        }
        case CBIND_TIME_ID:
        {
            PTIME_STRUCT *ret;
            SV *temporal;
            SV *rv;
            
            Newx( ret, 1, PTIME_STRUCT);
            RUNNEWARGM(pbind_get_arg_as_time(h_db, argnum, ret, &isnull));
            temporal = newSV(0);
            rv = newRV_noinc(temporal);
            sv_setref_pv(rv, "PTIME_STRUCTPtr", ret);
            sv_setsv(sv, rv);
            SvREFCNT_dec(rv);
            break;
        }
        case CBIND_DATE_ID:
        {
            PDATE_STRUCT *ret;
            SV *temporal;
            SV *rv;
            
            Newx( ret, 1, PDATE_STRUCT);
            push_mem_stack(mem_stack, p_tos, ret, MEM_VOID);
            RUNNEWARGM(pbind_get_arg_as_date(h_db, argnum, ret, &isnull));
            pop_mem_stack(p_tos);
            temporal = newSV(0);
            rv = newRV_noinc(temporal);
            sv_setref_pv(rv, "PDATE_STRUCTPtr", ret);
            sv_setsv(sv, rv);
            SvREFCNT_dec(rv);
            break;
	}
	case CBIND_MV_DATE_ID:
	{
		PDATE_STRUCT *ret;
		SV *temporal;
		SV *rv;

		Newx( ret, 1, PDATE_STRUCT);
		push_mem_stack(mem_stack, p_tos, ret, MEM_VOID);
		RUNNEWARGM(pbind_get_arg_as_date(h_db, argnum, ret, &isnull));
		pop_mem_stack(p_tos);
		temporal = newSV(0);
		rv = newRV_noinc(temporal);
		sv_setref_pv(rv, "PDATE_STRUCTPtr", ret);
		sv_setsv(sv, rv);
		SvREFCNT_dec(rv);
		break;
	}
        case CBIND_TIMESTAMP_ID:
        {
            PTIMESTAMP_STRUCT *ret;
            SV *temporal;
            SV *rv;

            Newx( ret, 1, PTIMESTAMP_STRUCT);
            push_mem_stack(mem_stack, p_tos, ret,MEM_VOID);
            RUNNEWARGM(pbind_get_arg_as_timestamp(h_db, argnum, ret, &isnull));
            pop_mem_stack(p_tos);
            temporal = newSV(0);
            rv = newRV_noinc(temporal);
            sv_setref_pv(rv, "PTIMESTAMP_STRUCTPtr", ret);
            sv_setsv(sv, rv);
            SvREFCNT_dec(rv);
            break;
        }
        case CBIND_BOOL_ID:
        {
            bool_t val;
            RUNNEWARGM(cbind_get_arg_as_bool(h_db, argnum, &val, &isnull));
            sv_setiv(sv, val);
            break;
        }
        case CBIND_CURRENCY_ID:
        {
            double val;
            RUNNEWARGM(cbind_get_arg_as_cy(h_db, argnum, &val, &isnull));
            sv_setnv(sv, val);
            break;
        }
        case CBIND_DLIST_ID:
        {
            char buf[MAX_BUF];
            char *p;
            byte_size_t size;
            int n;
            int i;
            AV *av;
            bool_t flag;
            int elem_size;
            SV *rv;
            int save_tos;
            char *p_buf;
            SV *tempsv;

            save_tos = *p_tos;

			// get dlist
			//warn("processing list\n");
            RUNNEWARGM(cbind_get_arg_as_dlist(h_db, argnum, NULL, 0, &size, &isnull));
            if (size <= sizeof(buf)) {
                p_buf = buf;
            } else {
                Newx( p_buf, size, char);
                push_mem_stack(mem_stack, p_tos, p_buf,MEM_VOID);
            }
            RUNNEWARGM(cbind_get_arg_as_dlist(h_db, argnum, p_buf, size, &size, &isnull));	    
            // calculate number of elements in dlist
            RUNNEWARGM(cbind_dlist_calc_num_elems(p_buf, size, &n));
            // get empty array
            av = newAV();
            p = p_buf;
            for (i=0; i < n; i++) {
                RUNNEWARGM(cbind_dlist_is_elem_null(p,&flag));
                if (flag) { // process null MUST BE PROCESSED FIRST before test for string
                        
                    RUNNEWARGM(cbind_dlist_get_elem_size(p, &elem_size));
                    tempsv = newSV(0);
                    av_push(av, tempsv);
                    //SvREFCNT_dec(tempsv);
                    goto loop;
                }
                RUNNEWARGM(cbind_dlist_is_elem_int(p,&flag));
                if (flag) { // process integer
                    int val;
					RUN(cbind_dlist_get_elem_as_int(p, &val, &elem_size));
					tempsv = newSViv(val);
					av_push(av,tempsv);
					//SvREFCNT_dec(tempsv);
                    //warn("processing integer %d\n",val);                    
                    goto loop;
                }
                RUNNEWARGM(cbind_dlist_is_elem_double(p,&flag));
                if (flag) { // process double
                    double val;
                    RUN(cbind_dlist_get_elem_as_double(p, &val, &elem_size));
					//warn("processing double %g\n",val);
					tempsv = newSVnv(val);
					av_push(av,tempsv);
					//SvREFCNT_dec(tempsv);
                    goto loop;
                }
                RUNNEWARGM(cbind_dlist_is_elem_str(p,&flag));
                if (flag) { // process string
                    const char *str;
                    int size;
                    bool_t is_uni;
                    
                    RUN(cbind_dlist_get_str_elem(p, &is_uni, &str, &size, &elem_size));
                    if (is_uni == 0) {
                        //sv_setpvn(sv, str, size);
                        //warn("processing string %.*s size=%d\n",size,str,size);
						if (size !=0) {
							//printf("processing string\n");
							tempsv = newSVpv(str,size);
							av_push(av, tempsv);
							//SvREFCNT_dec(tempsv);							
							
						}
						else {
							tempsv = newSVpv("",0);
							av_push(av,tempsv);
							//SvREFCNT_dec(tempsv);							
                        }
                    } else {
                        int dest_size;
                        char *dest = NULL;
                        SV *newSV;

                        dest_size = get_size_uni_to_utf8((wchar_t*)str, size);
                        if (dest_size > 0) {
                            Newx(dest, dest_size, char);
                            push_mem_stack(mem_stack, p_tos, dest,MEM_VOID);
                            RUN(cbind_uni_to_utf8((wchar_t*)str, (char_size_t)size/sizeof(wchar_t), dest, dest_size,&dest_size));
                            newSV = newSVpv(dest,dest_size);
                        } else {
                            newSV = newSVpv("",0);
                        }

                        SvUTF8_on(newSV);
                        av_push(av,newSV);
                        //sv_2mortal(newSV);						
                        Safefree(dest);
                    }
                    
                    goto loop;
                }
               
loop:
                p += elem_size;
            }
            *p_tos = save_tos;
            rv = newRV_noinc((SV*)av);
            sv_setsv(sv, rv);
            SvREFCNT_dec(rv);
            if (size > sizeof(buf)) {
                Safefree(p_buf);
                pop_mem_stack(p_tos);
            }
	    
            break;

        }
        default:
            Perl_croak(aTHX_ "unknown type for argument, type = %d class_name=%s method name = %s argnum=%d", cpp_type, class_name, mtd_name, argnum);


    }
}

void query_get_data(h_query query, SV* sv, int i, Mem_Ptr mem_stack[], int *p_tos)
{
    int typ;
    bool_t is_null;
    
    RUN(cbind_query_get_col_sql_type(query, i, &typ));
    //warn("i=%d typ=%d\n", i, typ);
    switch (typ) {
        case SQL_CHAR:
        case SQL_VARCHAR:
        case SQL_LONGVARCHAR:
        {

            char buf[MAX_BUF];
            int size;
            
            RUN(cbind_query_get_mb_str_data(query, buf, sizeof(buf), &size, &is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }

            if (size > 0) sv_setpvn(sv, buf, size);
            break;
            
        }
        case SQL_WCHAR:
        case SQL_WVARCHAR:
        case SQL_WLONGVARCHAR:
        {

            wchar_t unistr[MAX_BUF];
            wchar_t *p_unistr;
            int unisize;
            char utf8str[MAX_BUF];
            char *p_utf8str;
            int utf8size;

            p_unistr = unistr;
            unisize = sizeof(unistr);

            RUN(cbind_query_get_uni_str_data(query, p_unistr, unisize, &unisize,&is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }
            
            utf8size = get_size_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t));            

            if (utf8size <= sizeof(utf8str))
                p_utf8str = utf8str;
            else {
                Newx( p_utf8str, utf8size, char);
                push_mem_stack(mem_stack, p_tos, p_utf8str,MEM_VOID);

            }
            RUN(cbind_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t), p_utf8str, utf8size, &utf8size));            
            if (utf8size > 0) sv_setpvn(sv, p_utf8str, utf8size);
            SvUTF8_on(sv);
            if (utf8size >= sizeof(utf8str)) {
                Safefree(p_utf8str);
                pop_mem_stack(p_tos);
            }

            
            break;
            
        }
        case SQL_BINARY:
        case SQL_LONGVARBINARY:
        case SQL_VARBINARY:
            
        {

            SV *svtmp;
            char buf[MAX_BUF];
            int size;

            RUN(cbind_query_get_bin_data(query, buf, sizeof(buf), &size, &is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }
            
            svtmp = Binary2SV(buf, size);
            sv_setsv(sv, svtmp);
            SvREFCNT_dec(svtmp);
            break;
        }
        case SQL_TINYINT:
        case SQL_SMALLINT:
        case SQL_INTEGER:
        case SQL_BIGINT:
        case SQL_BIT:
        {
			__int64 val64;
			int val;
			char digits[22];
			RUN(cbind_query_get_int64_data(query, &val64, &is_null));
			if (is_null != 0) {
				sv_setsv(sv, &PL_sv_undef);
				return;
			}			
			if (val64 >= INT_MIN && val64 <= INT_MAX) {
				val = (int)val64;
				sv_setiv(sv, val);
			} else {
				i64toa(val64, digits, 10);
				sv_setpv(sv, digits);
			}
			break;
		}
        case SQL_FLOAT:
        case SQL_DOUBLE:
        case SQL_REAL:
        case SQL_NUMERIC:
        case SQL_DECIMAL:
        {
            double res;
            RUN(cbind_query_get_double_data(query, &res, &is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }
            
            sv_setnv(sv, res);            
            break;
        }
        case SQL_DATE:
        {
            PDATE_STRUCT* date_struct;
            
            Newx( date_struct, 1, PDATE_STRUCT);
            push_mem_stack(mem_stack, p_tos, date_struct,MEM_VOID);
            RUNM(pbind_query_get_date_data(query, date_struct, &is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }
            
            sv_setref_pv(sv, "PDATE_STRUCTPtr", date_struct);
            pop_mem_stack(p_tos);
            
            break;
        }
        case SQL_TIME:
        {
            PTIME_STRUCT* time_struct;

            Newx( time_struct, 1, PTIME_STRUCT);
            push_mem_stack(mem_stack, p_tos, time_struct,MEM_VOID);
            RUNM(pbind_query_get_time_data(query, time_struct, &is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }
            
            sv_setref_pv(sv, "PTIME_STRUCTPtr", time_struct);
            pop_mem_stack(p_tos);
            break;
        }
        case SQL_TIMESTAMP:
        {
            PTIMESTAMP_STRUCT* timestamp_struct;

            Newx( timestamp_struct, 1, PTIMESTAMP_STRUCT);
            push_mem_stack(mem_stack, p_tos, timestamp_struct,MEM_VOID);
            RUNM(pbind_query_get_timestamp_data(query, timestamp_struct, &is_null));
            if (is_null != 0) {
                sv_setsv(sv, &PL_sv_undef);
                return;
            }
            
            sv_setref_pv(sv, "PTIMESTAMP_STRUCTPtr", timestamp_struct);
            pop_mem_stack(p_tos);
            break;
        }
        default:
            Perl_croak(aTHX_ "unknown sql type = %d for column = %d",typ, i);  
            
    }
   
}

void query_set_par(h_query query, SV* sv, int i, Mem_Ptr mem_stack[], int *p_tos)
{
    int typ;
    
    RUN(cbind_query_get_par_sql_type(query, i, &typ));
    //warn("i=%d typ=%d\n", i, typ);
    switch (typ) {
        case SQL_CHAR:
        case SQL_VARCHAR:
        case SQL_LONGVARCHAR:
        {
            STRLEN len;
            wchar_t unistr[MAX_BUF];
            int unisize;
            wchar_t *p_unistr;
            char *p_utf8str;

            sv_utf8_upgrade(sv);
            p_utf8str = SvPV(sv, len);

            unisize = get_size_utf8_to_uni(p_utf8str, (int) len);            
            if (len > 0 && unisize==0) Perl_croak(aTHX_ "file=%s line=%d, Bad UTF8 string\n", __FILE__, __LINE__);            
			unisize++;
            if (unisize < sizeof(unistr)) {
                p_unistr = unistr;
            } else {
                Newx( p_unistr, unisize, wchar_t);
                push_mem_stack(mem_stack, p_tos, p_unistr,MEM_VOID);
            }
            cbind_utf8_to_uni(p_utf8str, (int)len, p_unistr, sizeof(wchar_t)*unisize, &unisize);            
            //warn("var.cpp_type=%d var.obj.oref=%d\n", var->cpp_type,
            //var->obj.oref);
            RUN(cbind_query_set_uni_str_par(query, i, p_unistr, unisize));
            if (unisize >= sizeof(unistr)) {
                Safefree(p_unistr);
                pop_mem_stack(p_tos);
            }
            break;
        }
        case SQL_WCHAR:
        case SQL_WVARCHAR:
        case SQL_WLONGVARCHAR:
        {
            STRLEN len;
            wchar_t unistr[MAX_BUF];
            int unisize;
            wchar_t *p_unistr;
            char *p_utf8str;

            sv_utf8_upgrade(sv);
            p_utf8str = SvPV(sv, len);
            unisize = get_size_utf8_to_uni(p_utf8str, (int) len);            
            if (len > 0 && unisize==0) Perl_croak(aTHX_ "file=%s line=%d, Bad UTF8 string\n", __FILE__, __LINE__);            
			unisize++;
            if (unisize < sizeof(unistr)) {
                p_unistr = unistr;
            } else {
                Newx( p_unistr, unisize, wchar_t);
                push_mem_stack(mem_stack, p_tos, p_unistr,MEM_VOID);
            }
            cbind_utf8_to_uni(p_utf8str, (int)len, p_unistr, sizeof(wchar_t)*unisize, &unisize);            
            //warn("var.cpp_type=%d var.obj.oref=%d\n", var->cpp_type,
            //var->obj.oref);
            RUN(cbind_query_set_uni_str_par(query, i, p_unistr, unisize));
            if (unisize >= sizeof(unistr)) {
                Safefree(p_unistr);
                pop_mem_stack(p_tos);
            }
            break;
        }
        case SQL_BINARY:
        case SQL_LONGVARBINARY:
        case SQL_VARBINARY:            
        {
            int len;
            char *buf = SV2Binary(sv, &len);
            RUN(cbind_query_set_bin_par(query, i, buf, len));
            Safefree(buf);
            break;
        }
        case SQL_TINYINT:
        case SQL_SMALLINT:
        case SQL_INTEGER:
        case SQL_BIGINT:
        case SQL_BIT:
        {

            RUN(cbind_query_set_int_par(query, i, (int)SvIV(sv)));
            break;
        }
        case SQL_FLOAT:
        case SQL_DOUBLE:
        case SQL_REAL:
        case SQL_NUMERIC:
        case SQL_DECIMAL:
        {
            RUN(cbind_query_set_double_par(query, i, (double)SvNV(sv)));            
            break;
        }
        case SQL_DATE:
        {
            IV tmp;
            PDATE_STRUCT *in;
            if (sv_isobject(sv) && sv_derived_from(sv, "PDATE_STRUCTPtr")) {
                tmp = SvIV((SV*)SvRV(sv));
                in = INT2PTR(PDATE_STRUCT *, tmp);
                RUN(pbind_query_set_date_par(query, i, in));
            } else {
                PDATE_STRUCT date_struct;
                SV *svdate;
                int rc;
                SV *rv;

                svdate = newSV(0); // svdate now points to ref
                rv = newRV_noinc(svdate);
                sv_setref_pv(rv, "PDATE_STRUCTPtr", &date_struct);
                rc = parsedate(sv,rv);
                RUN(pbind_query_set_date_par(query, i, &date_struct));
                if (rc != 0) Perl_croak(aTHX_ "expecting a valid date or a PDATE_STRUCTPtr");

            }
            
            break;
        }
        case SQL_TIME:
        {
            IV tmp;
            PTIME_STRUCT *in;
            if (sv_isobject(sv) && sv_derived_from(sv, "PTIME_STRUCTPtr")) {
                tmp = SvIV((SV*)SvRV(sv));
                in = INT2PTR(PTIME_STRUCT *, tmp);
                RUN(pbind_query_set_time_par(query, i, in));
            } else {
                PTIME_STRUCT time_struct;
                SV *svtime;
                int rc;
                SV *rv;
                
                svtime = newSV(0); // svdate now points to ref
                rv = newRV_noinc(svtime);
                sv_setref_pv(rv, "PTIME_STRUCTPtr", &time_struct);
                rc = parsetime(sv,rv);
                RUN(pbind_query_set_time_par(query, i, &time_struct));
                if (rc != 0) Perl_croak(aTHX_ "expecting a valid time or a PTIME_STRUCTPtr");
            }   
            break;
        }
        case SQL_TIMESTAMP:
        {
            IV tmp;
            PTIMESTAMP_STRUCT *in;
            if (sv_isobject(sv) && sv_derived_from(sv, "PTIMESTAMP_STRUCTPtr")) {
                tmp = SvIV((SV*)SvRV(sv));
                in = INT2PTR(PTIMESTAMP_STRUCT *, tmp);
                RUN(pbind_query_set_timestamp_par(query, i, in));
            } else {
                PTIMESTAMP_STRUCT timestamp_struct;
                SV *svtimestamp;
                int rc;
                SV *rv;
                
                svtimestamp = newSV(0); // svdate now points to ref
                rv = newRV_noinc(svtimestamp);
                sv_setref_pv(rv, "PTIMESTAMP_STRUCTPtr", &timestamp_struct);
                rc = parsetimestamp(sv,rv);
                RUN(pbind_query_set_timestamp_par(query, i, &timestamp_struct));
                if (rc != 0) Perl_croak(aTHX_ "expecting a valid timestamp or a PTIMESTAMP_STRUCTPtr");
            }
            break;
        }
        default:
            Perl_croak(aTHX_ "unknown sql type = %d for par = %d", typ, i);  
    }
}

SV *Binary2SV(char *buffer, int len)
{
    dSP;
    int count;
    int i;
    SV *retval;
    
    ENTER;
    SAVETMPS;
    PUSHMARK(SP);
    XPUSHs(sv_2mortal(newSVpv("c*",0)));
    for (i = 0; i < len; i++)
        XPUSHs(sv_2mortal(newSViv(buffer[i])));
    PUTBACK;
    
    count = call_method("Intersys::PERLBIND::pack", G_SCALAR);

    SPAGAIN;

    if (count != 1)
        Perl_croak(aTHX_ "calling Perl function pack failed");
    retval = newSVsv(POPs);
    
    PUTBACK;
    FREETMPS;
    LEAVE;
    return retval;
    
}

SV *make_status(int code, wchar_t *p_unistr, int unisize,int cpp_type, char *class_name, char *mtd_name, int argnum, Mem_Ptr mem_stack[], int *p_tos, int is_return)
{
    HV *hv;
    HV *stash;
    SV *rv;
    char utf8str[MAX_BUF];
    int utf8size;
    char *p_utf8str;
    SV *msgsv;

    utf8size = get_size_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t));
    if (utf8size <= sizeof(utf8str))
        p_utf8str = utf8str;
    else {
        Newx( p_utf8str, utf8size, char);
        push_mem_stack(mem_stack, p_tos, p_utf8str,MEM_VOID);

    }
    RUNNEWARGM(cbind_uni_to_utf8((wchar_t*)p_unistr, unisize/sizeof(wchar_t), p_utf8str, utf8size, &utf8size));
    p_utf8str[utf8size] = 0;
    msgsv = newSVpv(p_utf8str, utf8size);
    //sv_setpvn(msgsv, p_utf8str, utf8size);
    SvUTF8_on(msgsv);
    
    hv = newHV();
    hv_store(hv, "_code", sizeof("_code")-1, newSViv((IV)code), 0);
    hv_store(hv, "_msg", sizeof("_msg")-1, newSVsv(msgsv), 0); // array of objects to be freed when database is freed
    stash = gv_stashpv("Intersys::PERLBIND::Status",TRUE);
    rv = newRV_noinc((SV*)hv);
    sv_bless(rv,stash);
    if (utf8size > sizeof(utf8str)) {
        Safefree(p_utf8str);
        pop_mem_stack(p_tos);
	}
	if (is_return && code != 0 && code !=1) {
		Perl_croak(aTHX_ "code=%d message=%*s\n", code, utf8size, p_utf8str);

	}
	
    return rv;
}

SV *connhashrv(h_connection con)
{
    HV *hv;
    HV *stash;
    SV *rv;

    hv = newHV();
    hv_store(hv, "_connection", sizeof("_connection")-1, newSViv((IV)con), 0);
    stash = gv_stashpv("Intersys::PERLBIND::Connection",TRUE);
    rv = newRV_noinc((SV*)hv);
    sv_bless(rv,stash);
    return rv;
    
}

SV *databasehashrv(h_database db, SV *conn)
{
    SV *sv;
    HV *stash;
    SV *rv;
    Database *database;
    ObjectNode *head;
    ObjectNode *tail;
    QueryNode *qhead;
    QueryNode *qtail;

    sv = newSV(0);
    Newx( database, 1, Database);
    Newx( database->database_being_destroyed, 1, int);
    *(database->database_being_destroyed) = 0;
    strcpy(database->signature,"database");
    database->_database =  db;
    sv_setiv(sv, (long)database);
    rv = newRV_inc(SvRV(conn));
    database->_connection = rv;
    Newx( head, 1, ObjectNode);
    Newx( tail, 1, ObjectNode);
    head->next = tail;
    head->prev = head;
    tail->next = tail;
    tail->prev = head;
    database->object_list = head;
    Newx( qhead, 1, QueryNode);
    Newx( qtail, 1, QueryNode);
    qhead->next = qtail;
    qhead->prev = qhead;
    qtail->next = qtail;
    qtail->prev = qhead;
    database->query_list = qhead;
    
    stash = gv_stashpv("Intersys::PERLBIND::Database",TRUE);
    rv = newRV_noinc((SV*)sv);
    sv_bless(rv,stash);
    return rv;

}

SV *objectrv(my_var *var)
{
    SV *sv;
    HV *stash;
    SV *rv;
    Object *obj;
    
    //hv = (HV*)sv_2mortal((SV*)newHV());

    sv = newSV(0);
    Newx( obj, 1, Object);
    obj->_object =  var;
    sv_setiv(sv, (long)obj);
    stash = gv_stashpv("Intersys::PERLBIND::Object",TRUE);
    rv = newRV_noinc((SV*)sv);
    sv_bless(rv,stash);
    setobjid(rv, ++objid);
    setobjactive(rv,1);
    return rv;

}

SV *statusrv(int code, char* buf, int size, char* msg, int status_size)
{
    SV *sv;
    HV *stash;
    SV *rv;
    Status *obj;

    //hv = (HV*)sv_2mortal((SV*)newHV());

    sv = newSV(0);
    Newx( obj, 1, Status);
    obj->code =  code;
    obj->size = size;
    strncpy(obj->signature, "status", SIGNATURE_SIZE-1);
    obj->signature[SIGNATURE_SIZE-1] = 0;
    memcpy(obj->buf, buf, size);
    strncpy(obj->msg, msg, status_size);
    sv_setiv(sv, (long)obj);
    stash = gv_stashpv("Intersys::PERLBIND::Status",TRUE);
    rv = newRV_noinc((SV*)sv);
    sv_bless(rv,stash);
    return rv;

}

SV *queryrv(h_query hquery)
{
    SV *sv;
    HV *stash;
    SV *rv;
    Query *query;

    //hv = (HV*)sv_2mortal((SV*)newHV());

    sv = newSV(0);
    Newx( query, 1, Query);
    query->_query =  hquery;
    sv_setiv(sv, (long)query);
    stash = gv_stashpv("Intersys::PERLBIND::Query",TRUE);
    rv = newRV_noinc((SV*)sv);
    sv_bless(rv,stash);
    query->_queryid = ++queryid;
    query->_active = 1;
    return rv;

}

char * SV2Binary(SV *sv, int *plen)
{
    dSP;
    int count;
    int i;
    char *retval = NULL;

    ENTER;
    SAVETMPS;
    PUSHMARK(SP);
    XPUSHs(sv_2mortal(newSVpv("c*",0)));
    XPUSHs(sv_mortalcopy(sv));  // do we need the mortalcopy?
    PUTBACK;
    
    count = call_pv("Intersys::PERLBIND::unpack", G_ARRAY);

    SPAGAIN;

    if (count != 0) {
        Newx( retval, count, char);
        for (i = count-1; i >= 0; i--) {
            retval[i] = (char)POPi;
            //warn("retval[%d]=%d\n",i,retval[i]);
        }
    }
    *plen = count;
        
    PUTBACK;
    FREETMPS;
    LEAVE;
    return retval;

}

int parsedate(SV *svin, SV *refdate)
{
    dSP;
    int count;
    SV *retval;
    int rc;

    ENTER;
    SAVETMPS;
    PUSHMARK(SP);
    XPUSHs(svin);
    XPUSHs(refdate);
    PUTBACK;

    count = call_pv("PDATE_STRUCTPtr::parse", G_SCALAR);

    SPAGAIN;

    if (count != 1)
        Perl_croak(aTHX_ "calling Perl function pack failed");
    retval = newSVsv(POPs);  // return 0 if success, return code if failure
    rc = (int)SvIV(retval);
    PUTBACK;
    FREETMPS;
    LEAVE;
    return rc;

}

int parsedecimal(SV *svin, SV *refdecimal)
{
    dSP;
    int count;
    SV *retval;
    int rc;

    ENTER;
    SAVETMPS;
    PUSHMARK(SP);
    XPUSHs(svin);
    XPUSHs(refdecimal);
    PUTBACK;

    // 05-12-11
    count = call_pv("Intersys::PERLBIND::Decimal::parsedecimal", G_SCALAR);

    SPAGAIN;

    if (count != 1)
        Perl_croak(aTHX_ "calling Perl function pack failed");
    retval = newSVsv(POPs);  // return 0 if success, return code if failure
    rc = (int) SvIV(retval);
    PUTBACK;
    FREETMPS;
    LEAVE;
    return rc;

}

int parsetime(SV *svin, SV *reftime)
{
    dSP;
    int count;
    SV *retval;
    int rc;

    ENTER;
    SAVETMPS;
    PUSHMARK(SP);
    XPUSHs(svin);
    XPUSHs(reftime);
    PUTBACK;

    count = call_pv("PTIME_STRUCTPtr::parse", G_SCALAR);

    SPAGAIN;

    if (count != 1)
        Perl_croak(aTHX_ "calling Perl function pack failed");
    retval = newSVsv(POPs);  // return 0 if success, return code if failure
    rc = (int) SvIV(retval);
    PUTBACK;
    FREETMPS;
    LEAVE;
    return rc;

}

int parsetimestamp(SV *svin, SV *reftimestamp)
{
    dSP;
    int count;
    SV *retval;
    int rc;

    ENTER;
    SAVETMPS;
    PUSHMARK(SP);
    XPUSHs(svin);
    XPUSHs(reftimestamp);
    PUTBACK;

    count = call_pv("PTIMESTAMP_STRUCTPtr::parse", G_SCALAR);

    SPAGAIN;

    if (count != 1)
        Perl_croak(aTHX_ "calling Perl function pack failed");
    retval = newSVsv(POPs);  // return 0 if success, return code if failure
    rc = (int) SvIV(retval);
    PUTBACK;
    FREETMPS;
    LEAVE;
    return rc;

}

h_database get_db(SV *rdatabase)
{
    Database *database;
    database = get_database(rdatabase);
    if (database == NULL) Perl_croak(aTHX_ "database is NULL");
    return database->_database;
}

Database * get_database(SV *rdatabase)
{
    Database *database;
    IV tmp;
    
    //warn("in get_database\n");
    if (!SvOK(rdatabase)) {
        INVALID_OBJ_WARNING("robj is not defined in get_database_sv");
        return NULL;
    }

    tmp = SvIV(rdatabase);
    database = INT2PTR(Database *, tmp);
    if (strcmp(database->signature,"database") != 0) {
        warn("invalid database signature\n");
        return NULL;
    }
    return database;

}

h_connection get_connection(SV *sv)
{
    HV *hv;
    SV **svp;
    h_connection conn;

    hv = (HV*)SvRV(sv);
    svp = hv_fetch(hv, "_connection", sizeof("_connection")-1, 0);
    conn = (h_connection) SvIV(*svp);
    return conn;
}


SV * get_database_sv(SV *robj)
{
    SV *sv;
    IV tmp;
    Object *obj;
    SV *database;

    //warn("in get_database_sv\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in get_database_sv");
        return NULL;
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("rv is not reference in get_database_sv");
        return NULL;
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    database = obj->_database;
    if (!SvOK(database)) {
        INVALID_OBJ_WARNING("database is not defined in get_database_sv");
        return NULL;
    }
    
    return database;
    
}

my_var* get_var(SV *robj)
{
    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in get_var\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in get_var");
        return NULL;
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in get_var");
        return NULL;
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    return obj->_object;
}

Status* get_status(SV *robj)
{
    SV *sv;
    IV tmp;
    Status *status;

    //warn("in get_var\n");
    if (!SvOK(robj)) {
        Perl_croak(aTHX_ "file=%s line=%d bad status\n", __FILE__, __LINE__);
    }

    if (!SvROK(robj)) {
        Perl_croak(aTHX_ "file=%s line=%d bad status\n", __FILE__, __LINE__);
    }

    sv = SvRV(robj);
    tmp = SvIV(sv);
    status = INT2PTR(Status *, tmp);
    if (strcmp(status->signature,"status") != 0) {
        Perl_croak(aTHX_ "file=%s line=%d bad status signature\n", __FILE__, __LINE__);
    }
    
    return status;
}

Object* get_object(SV *robj)
{
    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in get object\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in get_var");
        return NULL;
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in get_var");
        return NULL;
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    return obj;
}

Query* get_query(SV *rquery)
{
    SV *sv;
    IV tmp;
    Query *query;

    //warn("in get object\n");
    if (!SvOK(rquery)) {
        INVALID_QUERY_WARNING("rquery is not defined in get_query");
        return NULL;
    }

    if (!SvROK(rquery)) {
        INVALID_QUERY_WARNING("rquery is not reference in get_query");
        return NULL;
    }
    sv = SvRV(rquery);
    tmp = SvIV(sv);
    query = INT2PTR(Query *, tmp);
    return query;
}

h_query get_query_handle(SV *query)
{
    return get_query(query)->_query;
}

void get_decimal(SV *decimal, __int64 *significand, schr *exponent)
{
    HV *hv;
    SV **svsigfnd;
    SV **svexp;

    hv = (HV*)SvRV(decimal);
    svsigfnd = hv_fetch(hv, "_significand", sizeof("_significand")-1, 0);
    svexp = hv_fetch(hv, "_exponent", sizeof("_exponent")-1, 0);
    *significand = (__int64) SvIV(*svsigfnd);
    *exponent = (schr) SvIV(*svexp);
    
}

SV *set_decimal(__int64 significand, schr exponent)
{
    HV *hv;
    HV *stash;
    SV *rv;

    hv = newHV();
    hv_store(hv, "_significand", sizeof("_significand")-1, newSViv((IV)significand), 0);
    hv_store(hv, "_exponent", sizeof("_exponent")-1, newSViv((IV)exponent), 0);
    stash = gv_stashpv("Intersys::PERLBIND::Decimal",TRUE);
    rv = newRV_noinc((SV*)hv);
    sv_bless(rv,stash);
    return rv;

}

void destroy_obj(Object *obj)
{
    my_var *var;
    if (obj == NULL) {
        INVALID_OBJ_WARNING("cannot destroy object since is NULL");
    }
    var = obj->_object;
    if (var == NULL) {
        INVALID_OBJ_WARNING1("cannot destroy var, it is NULL on object %x", obj);
    } else {
        //warn("destroying object $self variant=%x\n",var);
        //warn("origin = %s\n",var->origin);
        RUN(mycbind_object_clear(&var->v));
        //Safefree(&var->v);
        //warn("after safefree\n");
        Safefree(var);        
        obj->_object = NULL;
    }
    
}

void destroy_query(Query *query)
{
    h_query hquery;

    if (query == NULL) {
        INVALID_QUERY_WARNING("cannot destroy query since is NULL");
    }
    hquery = query->_query;
    if (hquery == 0) {
        INVALID_QUERY_WARNING1("cannot destroy query, it is NULL on query %x", query);
    } else {
        INVALID_QUERY_WARNING1("destroying query hquery=%x",hquery);
        RUN(cbind_query_close( hquery ));
        RUN(cbind_free_query(hquery));
        //RUN(cbind_free_query( hquery ));
        query->_query = 0;
    }
}

int getobjid(SV *robj)
{
    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in getobjid\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in getobjid");
        return 0;
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in getobjid");
        return 0;
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    return obj->_objid;
}

int getobjactive(SV *robj)
{
    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in getobjactive\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in getobjactive");
        return 0;
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in getobjactive");
        return 0;
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    return obj->_active;
}

void setdb(SV *robj, SV* dbhashsv)
{
    //SV *rv;
    SV *sv;
    IV tmp;
    Object *obj;
    Database *database;
    ObjectNode *head;
    ObjectNode *next;
    ObjectNode *curr;

    //warn("in setdb\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in setdb");
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in setdb");
    }
    if (!SvOK(dbhashsv)) {
        Perl_croak(aTHX_ "database is not valid SV");
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    obj->_database = dbhashsv;
    SvREFCNT_inc(dbhashsv);
    database = get_database(dbhashsv);
    obj->database_being_destroyed = database->database_being_destroyed;
    if (database == NULL) {
        Perl_croak(aTHX_" null database in setdb");
    }
    head = database->object_list;
    next = head->next;
    Newx( curr, 1, ObjectNode);
    next->prev = curr;
    head->next = curr;
    curr->next = next;
    curr->prev = head;
    curr->object = obj;  // link object into database
}

void setqdb(SV *rquery, SV* dbhashsv)
{
    //SV *rv;
    SV *sv;
    IV tmp;
    Query *query;
    Database *database;
    QueryNode *head;
    QueryNode *next;
    QueryNode *curr;

    //warn("in setdb\n");
    if (!SvOK(rquery)) {
        INVALID_QUERY_WARNING("rquery is not defined in setdb");
    }

    if (!SvROK(rquery)) {
        INVALID_QUERY_WARNING("rquery is not reference in setdb");
    }
    if (!SvOK(dbhashsv)) {
        Perl_croak(aTHX_ "database is not valid SV");
    }
    
    sv = SvRV(rquery);
    tmp = SvIV(sv);
    query = INT2PTR(Query *, tmp);
    query->_database = dbhashsv;
    SvREFCNT_inc(dbhashsv);
    database = get_database(dbhashsv);
    if (database == NULL) {
        Perl_croak(aTHX_" null database in setdb");
    }
    query->database_being_destroyed = database->database_being_destroyed;
    head = database->query_list;
    next = head->next;
    Newx( curr, 1, QueryNode);
    next->prev = curr;
    head->next = curr;
    curr->next = next;
    curr->prev = head;
    curr->query = query;  // link object into database
}

void setobjid(SV *robj, int objid)
{

    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in setobjid\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in setobjid");
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in setobjid");
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    obj->_objid = objid;

}

void setobjactive(SV *robj, int active)
{
    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in setobjactive\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in setobjactive");
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in setobjactive");
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    obj->_active = active;

}

void set_object(SV *robj, my_var* var_ref)
{
    SV *sv;
    IV tmp;
    Object *obj;

    //warn("in set_object\n");
    if (!SvOK(robj)) {
        INVALID_OBJ_WARNING("robj is not defined in set_object");
    }

    if (!SvROK(robj)) {
        INVALID_OBJ_WARNING("robj is not reference in set_object");
    }
    sv = SvRV(robj);
    tmp = SvIV(sv);
    obj = INT2PTR(Object *, tmp);
    obj->_object = var_ref;
}

void remove_object_from_database(SV *dbhashsv, Object *object)
{
    Database *database;
    ObjectNode *curr;
    ObjectNode *next;
    ObjectNode *prev;

    database = get_database(dbhashsv);
    if (database == NULL) {
        INVALID_OBJ_WARNING("cannot remove object from database since database is NULL\n");
        return;
    }
    curr = database->object_list;
    curr = curr->next;
    for (curr = curr->next; curr != curr->next;) {
        Object *currobj;        
        if (curr->next == curr) {
            break;
        }

        currobj = curr->object;
        next = curr->next;
        prev = curr->prev;
        if (object->_active && currobj->_objid && object->_objid && currobj->_objid == object->_objid) {
            currobj->_active = 0;
            //destroy_obj(currobj);
            prev->next = next;
            next->prev = prev;
            Safefree(curr);
        }
        curr = next;
    }
    
}

void remove_query_from_database(SV *dbhashsv, Query *query)
{
    Database *database;
    QueryNode *curr;
    QueryNode *next;
    QueryNode *prev;

    database = get_database(dbhashsv);
    if (database == NULL) {
        INVALID_OBJ_WARNING("cannot remove query from database since database is NULL\n");
        return;
    }
    curr = database->query_list;
    for (curr = curr->next; curr->next != curr;) {
        Query *currquery;
        currquery = curr->query;
        next = curr->next;
        prev = curr->prev;
        if (query->_active && currquery->_queryid && query->_queryid && currquery->_queryid == query->_queryid) {
            currquery->_active = 0;
            //destroy_query(currquery);
            prev->next = next;
            next->prev = prev;
            Safefree(curr);
        }
        curr = next;
    }

}

int copy_prop_info(pbind_prop_def *res)
{
    int retval;
    RUNPBIND(cbind_get_prop_cpp_type(res->prop_def, &res->cpp_type));
    RUNPBIND(cbind_get_prop_cache_type(res->prop_def, &res->cache_type));
    RUNPBIND(cbind_get_prop_name(res->prop_def, &res->name));
    return 0;

}

int pbind_get_prop_def(h_class_def cl_def,
                       const wchar_t* name,
                       pbind_prop_def *res,
                       Mem_Ptr mem_stack[],
                       int *p_tos)
{
    int retval;
    RUNPBIND(cbind_alloc_prop_def(&res->prop_def));
    push_mem_stack(mem_stack, p_tos, res->prop_def, MEM_PROP);
    RUNPBIND(cbind_get_prop_def(cl_def, name, res->prop_def));
    RUNPBIND(copy_prop_info(res));
    return 0;
}

int pbind_get_dyn_prop_def(h_database db,
                           h_objref oref,
                           const wchar_t* name,
                           pbind_prop_def *res,
                           Mem_Ptr mem_stack[],
                           int *p_tos)
{
    int retval;
    RUNPBIND(cbind_alloc_prop_def(&res->prop_def));
    push_mem_stack(mem_stack, p_tos, res->prop_def, MEM_PROP);
    RUNPBIND(cbind_get_dyn_prop_def(db, oref, name, res->prop_def));
    RUNPBIND(copy_prop_info(res));
    return 0;
}

int copy_mtd_info(pbind_mtd_def *res)
{
    int retval;
    RUNPBIND(cbind_get_mtd_is_func(res->mtd_def, &res->is_func));
    RUNPBIND(cbind_get_mtd_cpp_type(res->mtd_def, &res->cpp_type));
    RUNPBIND(cbind_get_mtd_cache_type(res->mtd_def, &res->cache_type));
    RUNPBIND(cbind_get_mtd_is_cls_mtd(res->mtd_def, &res->is_cls_mtd));
    RUNPBIND(cbind_get_mtd_num_args(res->mtd_def, &res->num_args));
    RUNPBIND(cbind_get_mtd_args_info(res->mtd_def, &res->args_info));
    RUNPBIND(cbind_get_mtd_name(res->mtd_def, &res->name));
    return 0;
}

int pbind_get_mtd_def(h_class_def cl_def,
                      const wchar_t* name,
                      pbind_mtd_def *res,
                      Mem_Ptr mem_stack[],
                      int *p_tos)
{
    int retval;
    RUNPBIND(cbind_alloc_mtd_def(&res->mtd_def));
    push_mem_stack(mem_stack, p_tos, res->mtd_def, MEM_MTD);
    RUNPBIND(cbind_get_mtd_def(cl_def, name, res->mtd_def));
    RUNPBIND(copy_mtd_info(res));
    return 0;
}

int pbind_get_dyn_mtd_def(h_database db,
                          h_objref oref,
                          const wchar_t *name,
                          pbind_mtd_def *res,
                          Mem_Ptr mem_stack[],
                          int *p_tos)
{
    int retval;
    RUNPBIND(cbind_alloc_mtd_def(&res->mtd_def));
    push_mem_stack(mem_stack, p_tos, res->mtd_def, MEM_MTD);
    RUNPBIND(cbind_get_dyn_mtd_def(db, oref, name, res->mtd_def));
    RUNPBIND(copy_mtd_info(res));
    return 0;
}


int pbind_mtd_rewind_args(pbind_mtd_def *res)
{
    int retval;
    RUNPBIND(cbind_mtd_rewind_args(res->mtd_def));
    return 0;
}

int copy_arg_info(pbind_arg_def *res)
{
    int retval;
    RUNPBIND(cbind_get_arg_cpp_type(res->arg_def, &res->cpp_type));
    RUNPBIND(cbind_get_arg_cache_type(res->arg_def, &res->cache_type));
    RUNPBIND(cbind_get_arg_name(res->arg_def, &res->name));
    RUNPBIND(cbind_get_arg_is_by_ref(res->arg_def, &res->is_by_ref));
    RUNPBIND(cbind_get_arg_is_default(res->arg_def, &res->is_default));    
    RUNPBIND(cbind_get_arg_def_val(res->arg_def, &res->def_val));
    RUNPBIND(cbind_get_arg_def_val_size(res->arg_def, &res->def_val_size));
    return 0;
}

int pbind_mtd_arg_get(pbind_mtd_def *mtd_def, pbind_arg_def *res)
{
    int retval;
    RUNPBIND(cbind_mtd_arg_get(mtd_def->mtd_def, res->arg_def));
    RUNPBIND(copy_arg_info(res));
    return 0;
}

int pbind_mtd_arg_next(pbind_mtd_def *mtd_def)
{
    int retval;
    RUNPBIND(cbind_mtd_arg_next(mtd_def->mtd_def));
    //RUNPBIND(copy_mtd_info(mtd_def->mtd_def));
    return 0;
}

int pbind_get_next_prop_def(h_class_def h_cl_def, pbind_prop_def *prop_def, bool_t *p_at_end)
{
    int retval;
    RUNPBIND(cbind_get_next_prop_def(h_cl_def, prop_def->prop_def, p_at_end));
    if (*p_at_end != 1) {
        RUNPBIND(copy_prop_info(prop_def));        
    }
    return 0;
}

int pbind_get_next_mtd_def(h_class_def h_cl_def, pbind_mtd_def *mtd_def, bool_t *p_at_end)
{
    int retval;
    RUNPBIND(cbind_get_next_mtd_def(h_cl_def, mtd_def->mtd_def, p_at_end));
    if (*p_at_end != 1) {
        RUNPBIND(copy_mtd_info(mtd_def));        
    }
    return 0;
    
}

int pbind_get_next_prop_def(h_class_def h_cl_def, pbind_prop_def *prop_def, bool_t *p_at_end);
int pbind_get_next_mtd_def(h_class_def h_cl_def, pbind_mtd_def *mtd_def, bool_t *p_at_end);

// date, time, timestamp functions
static int pbind_set_next_arg_as_time(h_database h_db, const PTIME_STRUCT* val, bool_t by_ref)
{
    return cbind_set_next_arg_as_time(h_db, val->hour, val->minute, val->second, by_ref);
}

static int pbind_set_next_arg_as_date(h_database h_db, const PDATE_STRUCT* val, bool_t by_ref)
{
    return cbind_set_next_arg_as_date(h_db, val->year, val->month, val->day, by_ref);
}

static int pbind_set_next_arg_as_mv_date(h_database h_db, const PDATE_STRUCT* val, bool_t by_ref)
{
	return cbind_set_next_arg_as_mv_date(h_db, val->year, val->month, val->day, by_ref);
}

static int pbind_set_next_arg_as_timestamp(h_database h_db, const PTIMESTAMP_STRUCT* val, bool_t by_ref)
{
    return cbind_set_next_arg_as_timestamp(h_db, val->year, val->month, val->day, val->hour, val->minute, val->second, val->fraction, by_ref);
}

static int pbind_get_arg_as_date(h_database h_db, int idx, PDATE_STRUCT* val, bool_t *p_is_null)
{
    return cbind_get_arg_as_date(h_db, idx, &val->year, &val->month, &val->day, p_is_null);
}

static int pbind_get_arg_as_time(h_database h_db, int idx, PTIME_STRUCT* val, bool_t *p_is_null)
{
    return cbind_get_arg_as_time(h_db, idx, &val->hour, &val->minute, &val->second, p_is_null);
}

static int pbind_get_arg_as_timestamp(h_database h_db, int idx, PTIMESTAMP_STRUCT* val, bool_t *p_is_null)
{
    return cbind_get_arg_as_timestamp(h_db, idx, &val->year, &val->month, &val->day, &val->hour, &val->minute, &val->second, &val->fraction, p_is_null);    
}
static int pbind_query_get_date_data(h_query _query, PDATE_STRUCT* val, bool_t *p_isnull)
{
    return cbind_query_get_date_data(_query, &val->year, &val->month, &val->day,p_isnull);
    
}
static int pbind_query_get_time_data(h_query _query, PTIME_STRUCT* val, bool_t *p_isnull)
{
    return cbind_query_get_time_data(_query, &val->hour, &val->minute, &val->second, p_isnull);
    
}

static int pbind_query_get_timestamp_data(h_query _query, PTIMESTAMP_STRUCT* val, bool_t *p_isnull)
{
    return cbind_query_get_timestamp_data(_query, &val->year, &val->month, &val->day, &val->hour, &val->minute, &val->second, &val->fraction, p_isnull);
    
}

static int pbind_query_set_date_par(h_query _query, int idx, const PDATE_STRUCT* val)
{
    return cbind_query_set_date_par(_query, idx, val->year, val->month, val->day);        
}
static int pbind_query_set_time_par(h_query _query, int idx, const PTIME_STRUCT* val)
{
    return cbind_query_set_time_par(_query, idx, val->hour, val->minute, val->second);    
    
}

static int pbind_query_set_timestamp_par(h_query _query, int idx, const PTIMESTAMP_STRUCT* val)
{
    return cbind_query_set_timestamp_par(_query, idx, val->year, val->month, val->day, val->hour, val->minute, val->second, val->fraction);        
}

MODULE = Intersys::PERLBIND		PACKAGE = Intersys::PERLBIND
PROTOTYPES:ENABLE

void destroylist(rvav)
SV* rvav
PREINIT:
    SV *sv;
CODE:
{
	
	sv = SvRV(rvav);
	if (SvTYPE(sv) == SVt_PVAV) {
		printf("got array, will destroy\n");
		av_undef((AV*)sv);
	}
}

	
char *
setlocale(category, locale)
int category;
char *locale;
PREINIT:
char *ret;
CODE:
{
    ret = cbind_setlocale(category, locale);
    RETVAL = ret;
}
OUTPUT:
    RETVAL

int
set_thread_locale(lcid)
int lcid;
PREINIT:
int ret;
CODE:
{
    ret = cbind_set_thread_locale(lcid);
    RETVAL = ret;
}
OUTPUT:
    RETVAL

char *
get_client_version()
PREINIT:
char *ret;
CODE:
{
    ret = (char*)cbind_get_client_version();
    RETVAL = ret;
}
OUTPUT:
    RETVAL


MODULE = Intersys::PERLBIND      PACKAGE = Intersys::PERLBIND::Connection
PROTOTYPES:ENABLE
SV*
new(class, conn_str, user, pwd, timeout)
  char *class
  char *conn_str
  char *user
  char *pwd
  int timeout
PREINIT:
h_connection res = 0;
wchar_t w_conn_str[MAX_CONNECTION_STRING_SIZE];
wchar_t w_user[MAX_CONNECTION_STRING_SIZE];
wchar_t w_pwd[MAX_CONNECTION_STRING_SIZE];
int size;
SV *rv;
CODE:
{
    RUN(cbind_mb_to_uni(conn_str, (byte_size_t)strlen(conn_str), w_conn_str, (char_size_t)sizeof(w_conn_str),&size));
    //warn("conn_str=%s\n", conn_str);
    //warn("size=%d\n",size);
    w_conn_str[size] = 0;
    //printw("conn=",w_conn_str);
    RUN(cbind_mb_to_uni(user, (byte_size_t)strlen(user), w_user, (char_size_t)sizeof(w_user),&size));
    w_user[size] = 0;
    RUN(cbind_mb_to_uni(pwd, (byte_size_t)strlen(pwd), w_pwd, (char_size_t)sizeof(w_pwd),&size));
    w_pwd[size] = 0;
    RUN(cbind_alloc_conn(w_conn_str, w_user, w_pwd, timeout, (void*)&res));
    rv = connhashrv(res);
    RETVAL = rv;
}
OUTPUT:
 RETVAL

SV*
new_secure(class, conn_str, srv_principal_name, security_level, timeout)
  char *class
  char *conn_str
  char *srv_principal_name
  int security_level
  int timeout
PREINIT:
h_connection res = 0;
wchar_t w_conn_str[MAX_CONNECTION_STRING_SIZE];
wchar_t w_srv_principal_name[MAX_CONNECTION_STRING_SIZE];
int size;
SV *rv;
CODE:
{
    RUN(cbind_mb_to_uni(conn_str, (byte_size_t)strlen(conn_str), w_conn_str, (char_size_t)sizeof(w_conn_str),&size));
    //warn("conn_str=%s\n", conn_str);
    //warn("size=%d\n",size);
    w_conn_str[size] = 0;
    //printw("conn=",w_conn_str);
    RUN(cbind_mb_to_uni(srv_principal_name, (byte_size_t)strlen(srv_principal_name), w_srv_principal_name, (char_size_t)sizeof(w_srv_principal_name),&size));
    w_srv_principal_name[size] = 0;
    RUN(cbind_alloc_secure_conn(w_conn_str, w_srv_principal_name, security_level, timeout, (void*)&res));
    rv = connhashrv(res);
    RETVAL = rv;
}
OUTPUT:
 RETVAL
                 
void 
DESTROY(conn)
SV *conn
CODE:
{

     h_connection conn1;

     conn1 = get_connection(conn);
     DEBUG_DESTROY("destroying connection\n");     
     RUN(cbind_free_conn( conn1));
}

int refcnt(conn)
SV* conn
CODE:
{
    RETVAL = SvREFCNT(SvRV(conn));
}
OUTPUT:
RETVAL

int
is_two_factor_enabled(conn)
        SV* conn
PREINIT:
        bool_t res;
CODE:
{
    RUN(cbind_is_two_factor_enabled(get_connection(conn),&res));
    RETVAL = res;
}
OUTPUT:
 RETVAL

int
send_two_factor_token(conn,token)
        SV* conn
        char *token
PREINIT:
wchar_t w_token[MAX_TWO_FACTOR_TOKEN];
int size;
bool_t res;
CODE:
{
    RUN(cbind_mb_to_uni(token, (byte_size_t)strlen(token), w_token, (char_size_t)sizeof(w_token),&size));
    w_token[size] = 0;
    RUN(cbind_send_two_factor_token(get_connection(conn),w_token,&res));
    RETVAL = res;
}
OUTPUT:
 RETVAL



MODULE = Intersys::PERLBIND      PACKAGE = Intersys::PERLBIND::Database

SV *
new(class,conn)
SV *conn
PREINIT:
h_database db;
SV *rv;
CODE: 
{
    h_connection conn1;

    conn1 = get_connection(conn);
    RUN(cbind_alloc_db(conn1, &db));
    rv = databasehashrv(db,conn);
    cbind_set_ignore_null(0);
    RETVAL = rv;
}
OUTPUT:
 RETVAL

MODULE = Intersys::PERLBIND      PACKAGE = Intersys::PERLBIND::Database
void 
DESTROY(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
  ObjectNode *node;
  QueryNode *qnode;
  Database *database;
  ObjectNode *curr;
  QueryNode *qcurr;
CODE:
  {
    DEBUG_DESTROY1("in destroy database dbhashrv=%x\n",SvRV(dbhashrv));
    database = get_database(SvRV(dbhashrv));

    if (database == NULL) {
        warn("cannot destroy database since is NULL\n");
        return;
    }
    *(database->database_being_destroyed) = 1;
    node = database->object_list;
    curr = node->next;
    while (curr->next != curr) {
        Object *obj;
        obj = curr->object;
        DEBUG_DESTROY1("destroying obj %d in destroying database\n", obj->_objid);
        destroy_obj(obj);
        curr = curr->next;
    }
    qnode = database->query_list;
    qcurr = qnode->next;
    while (qcurr->next != qcurr) {
        Query *query;
        query = qcurr->query;
        DEBUG_DESTROY1("destroying query %d in destroying database\n", query->_queryid);        
        destroy_query(query);
        qcurr = qcurr->next;
    }
    
    SvREFCNT_dec(SvRV(database->_connection));
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_free_db( db ));
    DEBUG_DESTROY("after destroying database\n");
}

int refcnt(dbhashrv)
  SV* dbhashrv
CODE:
{
    RETVAL = SvREFCNT(SvRV(dbhashrv));
}
OUTPUT:
  RETVAL

void 
tstart(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
CODE:
  {
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_tstart( db ));
  }

void 
tcommit(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
CODE:
  {
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_tcommit( db ));
  }

void 
trollback(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
CODE:
  {
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_trollback( db ));
  }

int
tlevel(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
  int level;
CODE:
  {
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_tlevel( db, &level ));
    RETVAL = level;
  }
OUTPUT:
    RETVAL

int
is_uni_srv(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
  bool_t ref;
CODE:
  {
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_is_uni_srv( db, &ref ));
    RETVAL = ref;
  }
OUTPUT:
    RETVAL

void 
sync_cache(dbhashrv)
  SV * dbhashrv;
PREINIT:
  h_database db;
CODE:
  {
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_sync_cache( db ));
  }


MODULE = Intersys::PERLBIND      PACKAGE = Intersys::PERLBIND::Database
                                           
SV *
open(dbhashrv, type, oid, concurrency, timeout)
  SV * dbhashrv
  char* type
  char* oid
  int concurrency
  int timeout
PREINIT:
  h_database db;
  wchar_t w_type[MAX_TYPE_SIZE];
  wchar_t *pw_type;
  int type_utf8_size;
  int type_size;
  SV *object_rv;
  my_var *res;
  h_objref oref;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
  {
    type_utf8_size = (int)strlen(type);
    type_size = get_size_utf8_to_uni(type, type_utf8_size);
    if (type_size < sizeof(w_type)/sizeof(wchar_t)) {
        pw_type = w_type;
    } else {
        Newx( pw_type, type_size+1, wchar_t);
        push_mem_stack(mem_stack, &tos, pw_type, MEM_VOID);
    }
    cbind_utf8_to_uni(type, type_utf8_size, pw_type, type_size, &type_size);
    pw_type[type_size] = 0;

	db = get_db(SvRV(dbhashrv));
	RUN(cbind_reset_args(db));	
    Newx( res, 1, my_var);
    mycbind_obj_init(&res->v);
    res->origin = "open";
    RUN(cbind_open(db, pw_type, oid, concurrency, timeout, &oref));
    mycbind_set_obj(&res->v, oref, db, pw_type);
    object_rv = objectrv(res);
    setdb(object_rv, SvRV(dbhashrv));
    if (type_size >= sizeof(w_type)/sizeof(wchar_t)) {
        pop_mem_stack(&tos);        
    }
    
    RETVAL = object_rv;
}
OUTPUT:
  RETVAL

SV *
openid(dbhashrv, type, id, concurrency, timeout)
  SV* dbhashrv
  char* type
  char* id
  int concurrency
  int timeout
PREINIT:
  h_database db;
  wchar_t w_type[MAX_TYPE_SIZE];
  wchar_t *pw_type;
  int type_utf8_size;
  int type_size;
  wchar_t w_id[MAX_ID_SIZE];
  wchar_t *pw_id;
  int id_utf8_size;
  int id_size;
  my_var* res;
  SV *sv;
  SV *object_rv;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
  h_objref oref;
CODE:
{
	db = get_db(SvRV(dbhashrv));
    RUN(cbind_reset_args(db));

    type_utf8_size = (int)strlen(type);
    type_size = get_size_utf8_to_uni(type, type_utf8_size);
    if (type_size < sizeof(w_type)/sizeof(wchar_t)) {
        pw_type = w_type;
    } else {
        Newx( pw_type, type_size+1, wchar_t);
        push_mem_stack(mem_stack, &tos, pw_type, MEM_VOID);
    }
    cbind_utf8_to_uni(type, type_utf8_size, pw_type, type_size, &type_size);
    pw_type[type_size] = 0;

    id_utf8_size = (int)strlen(id);
    id_size = get_size_utf8_to_uni(id, id_utf8_size);
    if (id_size < sizeof(w_id)/sizeof(wchar_t)) {
        pw_id = w_id;
    } else {
        Newx( pw_id, id_size+1, wchar_t);
        push_mem_stack(mem_stack, &tos, pw_id, MEM_VOID);
    }
    cbind_utf8_to_uni(id, id_utf8_size, pw_id, id_size, &id_size);
    pw_id[id_size] = 0;

    //warn("concurrency=%d\n",concurrency);
    //warn("timeout=%d\n",timeout);
    Newx( res, 1, my_var);
    mycbind_obj_init(&res->v);    
    push_mem_stack(mem_stack, &tos, res, MEM_VOID);

    RUN(cbind_openid(db, pw_type, pw_id, concurrency, timeout, &oref));
    mycbind_set_obj(&res->v, oref, db, pw_type);
    pop_mem_stack(&tos);
    res->origin = "openid";
    sv = newSV(0);
    //sv = newSV(0);
    object_rv = objectrv(res);
    setdb(object_rv, SvRV(dbhashrv));
    if (type_size >= sizeof(w_type)/sizeof(wchar_t)) {
        pop_mem_stack(&tos);        
    }

    if (id_size >= sizeof(w_id)/sizeof(wchar_t)) {
        pop_mem_stack(&tos);        
    }

    
    RETVAL = object_rv;
}
OUTPUT:
  RETVAL

SV *
create_new(dbhashrv, type, sv_init_val)
  SV *dbhashrv
  char* type
  SV* sv_init_val
PREINIT:
  char *init_val;
  h_database db;
  wchar_t w_type[MAX_TYPE_SIZE];
  wchar_t *pw_type;
  wchar_t w_init_val[MAX_TYPE_SIZE];
  wchar_t *pw_init_val;
  my_var* res;
  int type_utf8_size;
  int type_size;
  int init_val_size;
  STRLEN init_val_utf8_size;
  SV *object_rv;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
  h_objref oref;
CODE:
{
	db = get_db(SvRV(dbhashrv));
    RUN(cbind_reset_args(db));

    type_utf8_size = (int)strlen(type);
    type_size = get_size_utf8_to_uni(type, type_utf8_size);
    if (type_size < sizeof(w_type)/sizeof(wchar_t)) {
        pw_type = w_type;
    } else {
        Newx( pw_type, type_size+1, wchar_t);
        push_mem_stack(mem_stack, &tos, pw_type, MEM_VOID);
    }
    cbind_utf8_to_uni(type, type_utf8_size, pw_type, type_size, &type_size);
    pw_type[type_size] = 0;

    if (SvOK(sv_init_val)) {
        init_val = SvPV(sv_init_val, init_val_utf8_size);
        init_val_size = get_size_utf8_to_uni(init_val, (int) init_val_utf8_size);
        
        if (init_val_size < sizeof(w_init_val)/sizeof(wchar_t)) {
            pw_init_val = w_init_val;
        } else {
            Newx( pw_init_val, init_val_size+1, wchar_t);
            push_mem_stack(mem_stack, &tos, pw_init_val, MEM_VOID);
        }
        cbind_utf8_to_uni(init_val, (byte_size_t)init_val_utf8_size, pw_init_val, init_val_size, &init_val_size);
        pw_init_val[init_val_size] = 0;
    } else {
        init_val_utf8_size = 0;
        init_val = NULL;
        init_val_size = get_size_utf8_to_uni(init_val, (int)init_val_utf8_size);
        pw_init_val = NULL;
    }
    Newx( res, 1, my_var);
    mycbind_obj_init(&res->v);
    push_mem_stack(mem_stack, &tos, res, MEM_VOID);
    res->origin = "create_new\n";
    RUN(cbind_create_new(db, pw_type, pw_init_val, &oref));
    mycbind_set_obj(&res->v, oref, db, pw_type);
    pop_mem_stack(&tos);
    if (type_size >= sizeof(w_type)/sizeof(wchar_t)) {
        pop_mem_stack(&tos);        
    }
    if (init_val_size >= sizeof(w_init_val)/sizeof(wchar_t)) {
        pop_mem_stack(&tos);
    }
    object_rv = objectrv(res);
    setdb(object_rv, SvRV(dbhashrv));
    //warn("dbhashrv refcnt=%d\n", SvREFCNT(dbhashrv));
    //warn("creating_new object_rv refcnt=%d\n", SvREFCNT(object_rv));
    RETVAL = object_rv;
}
OUTPUT:
  RETVAL

SV * run_class_method(dbhashrv, cl_name, mtd_name, ...)
  SV* dbhashrv
  char * cl_name
  char * mtd_name
PREINIT:
  h_database db;
  SV* dbhashsv;    
  wchar_t w_cl_name[MAX_TYPE_SIZE];
  wchar_t w_mtd_name[MAX_TYPE_SIZE];
  h_class_def cl_def;
  pbind_mtd_def mtd_def;
  SV *sv;
  SV *ret;
  pbind_arg_def arg_def;
  int size;
  int num_args;
  int i;
  bool_t is_null;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
{
    if (items < 3) 
        Perl_croak(aTHX_ "Usage: db->run_class_method(cl_name, method_name, cvariant_arg1, cvariant_arg2, cvariant_arg3,...)");
	db = get_db(SvRV(dbhashrv));
	RUN(cbind_reset_args(db));		
    RUN(cbind_mb_to_uni(cl_name, (byte_size_t)strlen(cl_name), w_cl_name, (char_size_t)sizeof(w_cl_name),&size));
    w_cl_name[size] = 0;
    num_args = items - 3; // this is the number of passed in args but method may have fewer args
    RUN(cbind_alloc_class_def(db, w_cl_name, &cl_def));
    RUN(cbind_mb_to_uni(mtd_name, (byte_size_t)strlen(mtd_name), w_mtd_name, (char_size_t)sizeof(w_mtd_name),&size));
    w_mtd_name[size] = 0;
    RUN(pbind_get_mtd_def(cl_def, w_mtd_name, &mtd_def, mem_stack, &tos));
    if (mtd_def.num_args < num_args) num_args = mtd_def.num_args; // chop off extra args
    // copy Perl arguments to arguments
    RUN(pbind_mtd_rewind_args(&mtd_def));
    RUN(cbind_alloc_arg_def(&arg_def.arg_def));
    push_mem_stack(mem_stack, &tos, arg_def.arg_def, MEM_ARG);
    for (i = 0; i < num_args; ++i)
    {
        RUN(pbind_mtd_arg_get(&mtd_def, &arg_def));
        // process arg_def
        sv = ST(i+3);
        setSVasArg(sv, db, arg_def.cpp_type, arg_def.is_by_ref, w_cl_name, cl_name, mtd_name, i,mem_stack, &tos);
        RUN(pbind_mtd_arg_next(&mtd_def));
    }
    if (mtd_def.cpp_type != CBIND_VOID) {    
        RUN(cbind_set_next_arg_as_res(db, mtd_def.cpp_type));
    }
    RUN(cbind_run_method(db, -1, w_cl_name, w_mtd_name));
    ret = newSV(0);
    dbhashsv = SvRV(dbhashrv);
    if (mtd_def.cpp_type != CBIND_VOID) {
        getArgAsSV(ret, db, dbhashsv, &is_null, mtd_def.cpp_type, cl_name, mtd_name, num_args, mem_stack, &tos,1);
    }
    // copy any args by ref and clear variant
    RUN(pbind_mtd_rewind_args(&mtd_def));        
    for (i = 0; i < num_args; ++i)
    {
        RUN(pbind_mtd_arg_get(&mtd_def, &arg_def));
        if (arg_def.is_by_ref) {
            // process arg_def
            sv = ST(i+3);
            getArgAsSV(sv, db, dbhashrv, &is_null, arg_def.cpp_type, cl_name, mtd_name, i, mem_stack, &tos,0);
        }
        RUN(pbind_mtd_arg_next(&mtd_def));
        
    }
    
    RUN(cbind_free_class_def(db, cl_def));
    RUN(cbind_free_arg_def(arg_def.arg_def));
    pop_mem_stack(&tos);    
    RUN(cbind_free_mtd_def(mtd_def.mtd_def));
    pop_mem_stack(&tos);
    RETVAL = ret;
}
OUTPUT:
  RETVAL

SV *
alloc_query(dbhashrv)
  SV* dbhashrv
PREINIT:
  h_database db;
  h_query query;
  SV *query_rv;
CODE: 
{
    db = get_db(SvRV(dbhashrv));
    RUN(cbind_alloc_query(db, &query));
    query_rv = queryrv(query);
    setqdb(query_rv, SvRV(dbhashrv));
    RETVAL = query_rv;
}
OUTPUT:
 RETVAL

MODULE = Intersys::PERLBIND      PACKAGE = Intersys::PERLBIND::Object

void 
DESTROY(objectrv)
SV *objectrv
PREINIT:
SV *dbhashsv;
Object *my_object;
CODE:
{
    //warn("entering object destruction routine objectrv=%x refcnt=%d\n",objectrv,SvREFCNT(objectrv));

    if (!SvROK(objectrv)) {
        INVALID_OBJ_WARNING("object cannot be destroyed: is not a reference\n");
        return;
    }
    my_object = get_object(objectrv);
    if (my_object == NULL) {
        INVALID_OBJ_WARNING1("cannot destroy var, it is NULL on object %x\n", objectrv);
    } else {

        destroy_obj(my_object);
    }
    if (*(my_object->database_being_destroyed) == 1) return;
    
    // logic to destroy database follows, we don't destroy database in
    // destroying object if database is database_being_destroyed
    dbhashsv = get_database_sv(objectrv);
    if (dbhashsv != NULL) {
        Object *object;
        int refcnt;

       DEBUG_MEM("decrementing refcount of database refcount=%d\n", SvREFCNT(dbhashsv));        
       refcnt = SvREFCNT(dbhashsv);
       DEBUG_MEM("refcnt=%d before removing object from database",refcnt);
       if (refcnt > 0) {
            object = get_object(objectrv);
            //foobar active
            if (object != NULL && object->_active) {
                remove_object_from_database(dbhashsv, object);
                refcnt = SvREFCNT(dbhashsv);                
                if (refcnt > 0) {
                    SvREFCNT_dec(dbhashsv);
                    refcnt = SvREFCNT(SvRV(dbhashsv));
                    DEBUG_MEM("refcnt=%d after removing object from database",refcnt);
                }
            } else {
                INVALID_OBJ_WARNING("cannot remove object from database because is NULL\n");
            }
        }
    } else {
        INVALID_OBJ_WARNING("dbhashrv is NULL!\n");
    }
    // search for object on datbase list and remove it
    //warn("leaving object routine objectrv=%x\n",objectrv);
}

                                           
int refcnt(objectrv)
SV* objectrv
CODE:
{
    RETVAL = SvREFCNT(SvRV(objectrv));
}
OUTPUT:
RETVAL

int id(objectrv)
SV* objectrv
CODE:
{
    RETVAL = get_object(objectrv)->_objid;
}
OUTPUT:
RETVAL

int variant(objectrv)
SV *objectrv
PREINIT:
  my_var *var;
CODE:
{
    var = get_var(objectrv);
    RETVAL=(int)&var->v;
}
OUTPUT:
  RETVAL


SV* run_obj_method(objref, mtd_name, ...)
SV *objref
char *mtd_name
PREINIT:
  mycbind_obj* obj;
  my_var *var;
  wchar_t w_mtd_name[MAX_TYPE_SIZE];
  const wchar_t *w_cl_name;
  char class_name[MAX_CLASS_NAME]; // 1024
  h_class_def cl_def;
  h_database db;
  int oref;
  pbind_mtd_def mtd_def;
  SV *ret;
  pbind_arg_def arg_def;
  int size;
  int num_args;
  int i;
  SV *sv;
  SV *dbhashsv;
  bool_t is_null;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
{
    if (items < 2) 
        Perl_croak(aTHX_ "Usage: obj->run_obj_method(method_name, cvariant_arg1, cvariant_arg2, cvariant_arg3,...)");
    var = get_var(objref);
    obj = &var->v;
    dbhashsv = get_database_sv(objref);
    num_args = items - 2; // this is the number of passed in args but method may have fewer args
	RUN(mycbind_get_obj(obj, &oref, &db, &w_cl_name));
	RUN(cbind_reset_args(db));	
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &w_cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)w_cl_name, (char_size_t)wcslen(w_cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, w_cl_name, &cl_def));
    RUN(cbind_mb_to_uni(mtd_name, (byte_size_t)strlen(mtd_name), w_mtd_name, (char_size_t)sizeof(w_mtd_name),&size));
    w_mtd_name[size] = 0;
    RUN(pbind_get_dyn_mtd_def(db,  oref, w_mtd_name, &mtd_def, mem_stack, &tos));
    RUN(cbind_alloc_arg_def(&arg_def.arg_def));
    push_mem_stack(mem_stack, &tos, arg_def.arg_def, MEM_ARG);
    if (mtd_def.num_args < num_args) num_args = mtd_def.num_args; // chop off extra args
    // set Perl arguments as arguments
    RUN(pbind_mtd_rewind_args(&mtd_def));    
    for (i = 0; i < num_args; ++i)
    {
        RUN(pbind_mtd_arg_get(&mtd_def, &arg_def));
        // process arg_def
        sv = ST(i+2);
        setSVasArg(sv, db, arg_def.cpp_type, arg_def.is_by_ref, w_cl_name, class_name, mtd_name, i, mem_stack, &tos);	
        //warn("i=%d cpp_type=%d\n", i, arg_def.cpp_type);
        RUN(pbind_mtd_arg_next(&mtd_def));
    }
    //warn("num_args=%d\n",num_args);
    if (mtd_def.cpp_type != CBIND_VOID) {
        RUN(cbind_set_next_arg_as_res(db, mtd_def.cpp_type));
    }
    RUN(cbind_run_method(db, oref, w_cl_name, w_mtd_name));    
    //warn("after call\n");
    ret = newSV(0);
    if (mtd_def.cpp_type != CBIND_VOID) {
        getArgAsSV(ret, db, dbhashsv, &is_null, mtd_def.cpp_type, class_name, mtd_name, num_args, mem_stack, &tos,1);
	}
    // copy any args by ref and clear variant
    RUN(pbind_mtd_rewind_args(&mtd_def));        
    for (i = 0; i < num_args; ++i)
    {
        RUN(pbind_mtd_arg_get(&mtd_def, &arg_def));
        if (arg_def.is_by_ref) {
            // process arg_def
	    sv = ST(i+2);
	    getArgAsSV(sv, db, dbhashsv, &is_null, arg_def.cpp_type, class_name, mtd_name, i, mem_stack, &tos,0);
        }
        RUN(pbind_mtd_arg_next(&mtd_def));
        
    }
    
    RUN(cbind_free_class_def(db, cl_def));
    RUN(cbind_free_arg_def(arg_def.arg_def));
    pop_mem_stack(&tos);
    RUN(cbind_free_mtd_def(mtd_def.mtd_def));
    pop_mem_stack(&tos);
    RETVAL = ret;
}
OUTPUT:
  RETVAL
     
int is_method(objref, mtd_name)
SV* objref
char *mtd_name
PREINIT:
  mycbind_obj *obj;
  my_var *var;
  wchar_t w_mtd_name[MAX_TYPE_SIZE];
  const wchar_t *cl_name;
  char class_name[MAX_CLASS_NAME];
  h_class_def cl_def;
  h_database db;
  int oref;
  pbind_mtd_def mtd_def;
  int size;
  int err;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
{
    if (items < 2) 
        Perl_croak(aTHX_ "Usage: obj->run_obj_method(method_name, cvariant_arg1, cvariant_arg2, cvariant_arg3,...)");
    var = get_var(objref);
    obj = &var->v;
    RUN(mycbind_get_obj(obj, &oref, &db, &cl_name));
    //printf("cl_name=%ls\n", cl_name);fflush(stdout);
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)cl_name, (char_size_t)wcslen(cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, cl_name, &cl_def));
    RUN(cbind_mb_to_uni(mtd_name, (byte_size_t)strlen(mtd_name), w_mtd_name, (char_size_t)sizeof(w_mtd_name),&size));
    w_mtd_name[size] = 0;
    err = pbind_get_dyn_mtd_def(db, oref, w_mtd_name, &mtd_def, mem_stack, &tos);
    RUN(cbind_free_class_def(db, cl_def));
    RUN(cbind_free_mtd_def(mtd_def.mtd_def));
    pop_mem_stack(&tos);
    RETVAL=!err;
}
OUTPUT:
    RETVAL

SV *get(objref, prop_name)
SV* objref
char *prop_name
PREINIT:
  mycbind_obj *obj;
  my_var *var;
  wchar_t w_prop_name[MAX_TYPE_SIZE];
  const wchar_t *cl_name;
  char class_name[MAX_CLASS_NAME];
  char method_name[MAX_METHOD_NAME];
  h_class_def cl_def;
  h_database db;
  int oref;
  int size;
  pbind_prop_def prop_def;
  SV *ret;
  SV *dbhashsv;
  bool_t is_null;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
{
    if (items !=2) 
        Perl_croak(aTHX_ "Usage: obj->get(prop_name)");
    var = get_var(objref);
    obj = &var->v;
    dbhashsv = get_database_sv(objref);    
	RUN(mycbind_get_obj(obj, &oref, &db, &cl_name));
	RUN(cbind_reset_args(db));		
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)cl_name, (char_size_t)wcslen(cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, cl_name, &cl_def));
    RUN(cbind_mb_to_uni(prop_name, (byte_size_t)strlen(prop_name), w_prop_name, (char_size_t)sizeof(w_prop_name),&size));
    w_prop_name[size] = 0;
    RUN(pbind_get_dyn_prop_def(db, oref, w_prop_name, &prop_def, mem_stack, &tos));
    RUN(cbind_set_next_arg_as_res(db, prop_def.cpp_type));
    RUN(cbind_get_prop(db, oref, w_prop_name));
    ret = newSV(0);
    sprintf(method_name, "get%s\n", prop_name);    
    getArgAsSV(ret, db, dbhashsv, &is_null, prop_def.cpp_type, class_name, method_name, 0, mem_stack, &tos,0);
    RUN(cbind_free_class_def(db, cl_def));
    RUN(cbind_free_prop_def(prop_def.prop_def));
    RETVAL = ret;
}
OUTPUT:
  RETVAL

int set(objref, prop_name, val)
SV* objref
char *prop_name
SV *val
PREINIT:
  mycbind_obj *obj;
  my_var *var;
  wchar_t w_prop_name[MAX_TYPE_SIZE];
  char class_name[MAX_CLASS_NAME];
  char method_name[MAX_METHOD_NAME];
  const wchar_t *cl_name;
  h_class_def cl_def;
  h_database db;
  int oref;
  int size;
  pbind_prop_def prop_def;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
{
    if (items !=3) 
        Perl_croak(aTHX_ "Usage: obj->set(prop_name,val)");
    var = get_var(objref);
    obj = &var->v;
	RUN(mycbind_get_obj(obj, &oref, &db, &cl_name));
	RUN(cbind_reset_args(db));		
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)cl_name, (char_size_t)wcslen(cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, cl_name, &cl_def));
    RUN(cbind_mb_to_uni(prop_name, (byte_size_t)strlen(prop_name), w_prop_name, (char_size_t)sizeof(w_prop_name),&size));
    w_prop_name[size] = 0;
    RUN(pbind_get_dyn_prop_def(db, oref, w_prop_name, &prop_def, mem_stack, &tos));
    sprintf(method_name, "set%s\n", prop_name);
    setSVasArg(val, db, prop_def.cpp_type, 0, cl_name, class_name, method_name, 0, mem_stack, &tos);
    RUN(cbind_set_prop(db, oref, w_prop_name));
    RUN(cbind_free_prop_def(prop_def.prop_def));
    pop_mem_stack(&tos);
    RETVAL = 0;
}
OUTPUT:
  RETVAL

int is_property(objref, prop_name)
SV *objref
char *prop_name
PREINIT:
  mycbind_obj *obj;
  my_var *var;
  wchar_t w_prop_name[MAX_TYPE_SIZE];
  const wchar_t *cl_name;
  char class_name[MAX_CLASS_NAME];
  h_class_def cl_def;
  h_database db;
  int oref;
  int size;
  pbind_prop_def prop_def;
  int err;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
CODE:
{
    if (items !=2) 
        Perl_croak(aTHX_ "Usage: obj->get(prop_name)");
    var = get_var(objref);
    obj = &var->v;
    RUN(mycbind_get_obj(obj, &oref, &db, &cl_name));
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)cl_name, (char_size_t)wcslen(cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, cl_name, &cl_def));
    RUN(cbind_mb_to_uni(prop_name, (byte_size_t)strlen(prop_name), w_prop_name, (char_size_t)sizeof(w_prop_name),&size));
    w_prop_name[size] = 0;
    err = pbind_get_dyn_prop_def(db, oref, w_prop_name, &prop_def, mem_stack, &tos);
    RUN(cbind_free_class_def(db, cl_def));
    RUN(cbind_free_prop_def(prop_def.prop_def));
    pop_mem_stack(&tos);
    RETVAL = !err;
}
OUTPUT:
  RETVAL

int get_properties(objref)
SV *objref
PREINIT:
  mycbind_obj *obj;
  my_var *var;
  char prop_name[MAX_PROP_NAME];
  const wchar_t *cl_name;
  char class_name[MAX_CLASS_NAME];
  h_class_def cl_def;
  h_database db;
  int oref;
  int size;
  pbind_prop_def prop_def;
  bool_t at_end;
  U32 context;
  int num_props;
PPCODE:
{
    if (items !=1) 
        Perl_croak(aTHX_ "Usage: obj->get_properties()");
    context = GIMME_V;
    var = get_var(objref);
    obj = &var->v;
    RUN(mycbind_get_obj(obj, &oref, &db, &cl_name));
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)cl_name, (char_size_t)wcslen(cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, cl_name, &cl_def));
    RUN(cbind_reset_prop_defs(cl_def));
    RUN(cbind_alloc_prop_def(&prop_def.prop_def));
    num_props = 0;
    while (1) {
      RUN(pbind_get_next_prop_def(cl_def, &prop_def, &at_end));
      if (at_end) break;
      if (context == G_ARRAY) {
          RUN(cbind_uni_to_mb(prop_def.name, (char_size_t)wcslen(prop_def.name), prop_name, (byte_size_t)sizeof(prop_name)-1,&size));
          prop_name[size] = 0;
          PUSHs(sv_2mortal(newSVpv(prop_name, strlen(prop_name))));
      }
      num_props++;
    }
    if (context != G_ARRAY) {
        PUSHs(sv_2mortal(newSViv(num_props)));
    }
    RUN(cbind_free_class_def(db, cl_def));
    RETVAL = 0;
}

int get_methods(objref)
SV *objref
PREINIT:
  mycbind_obj *obj;
  my_var *var;
  char mtd_name[MAX_METHOD_NAME];
  const wchar_t *cl_name;
  char class_name[MAX_CLASS_NAME];
  h_class_def cl_def;
  h_database db;
  int oref;
  int size;
  pbind_mtd_def mtd_def;
  bool_t at_end;
  U32 context;
  int num_mtds;
PPCODE:
{
    if (items !=1) 
        Perl_croak(aTHX_ "Usage: obj->get_methods()");
    context = GIMME_V;
    var = get_var(objref);
    obj = &var->v;
    RUN(mycbind_get_obj(obj, &oref, &db, &cl_name));
    // get class name for new Ilya API
    //RUN(cbind_get_cl_name(obj, &cl_name));
    // set class_name
    RUN(cbind_uni_to_mb((wchar_t*)cl_name, (char_size_t)wcslen(cl_name), class_name, (byte_size_t)sizeof(class_name)-1,&size));
    class_name[size] = 0;
    RUN(cbind_alloc_class_def(db, cl_name, &cl_def));
    RUN(cbind_reset_mtd_defs(cl_def));
    num_mtds = 0;
    RUN(cbind_alloc_mtd_def(&mtd_def.mtd_def));
    while (1) {
      RUN(pbind_get_next_mtd_def(cl_def, &mtd_def, &at_end));
      if (at_end) break;
      if (context == G_ARRAY) {
          RUN(cbind_uni_to_mb(mtd_def.name, (char_size_t)wcslen(mtd_def.name), mtd_name, (byte_size_t)sizeof(mtd_name)-1,&size));
          mtd_name[size] = 0;
          PUSHs(sv_2mortal(newSVpv(mtd_name, strlen(mtd_name))));
      }
      num_mtds++;
    }
    if (context != G_ARRAY) {
        PUSHs(sv_2mortal(newSViv(num_mtds)));
    }
    RUN(cbind_free_class_def(db, cl_def));
    RETVAL = 0;
}

MODULE = Intersys::PERLBIND     PACKAGE = Intersys::PERLBIND::Status

char *toString(status_sv)
SV *status_sv;
PREINIT:
char *res;
CODE:
{
    Status *status = get_status(status_sv);
    res = status->msg;
    RETVAL=res;
}
OUTPUT:
RETVAL

int toCode(status_sv)
SV *status_sv;
PREINIT:
int res;
CODE:
{
    Status *status = get_status(status_sv);
    res = status->code;
    RETVAL=res;
}
OUTPUT:
RETVAL
                                     
void 
DESTROY(status_sv)
SV *status_sv;
CODE:
{

     Status *status = get_status(status_sv);
     Safefree(status);
}

MODULE = Intersys::PERLBIND      PACKAGE = Intersys::PERLBIND::Decimal
PROTOTYPES:ENABLE
SV*
new(class, significand, exponent)
  char *class
  IV significand
  IV exponent
PREINIT:
SV *rv;
CODE:
{
    rv = set_decimal((__int64)significand,(schr)exponent);
    RETVAL = rv;
}
OUTPUT:
 RETVAL
                                           
                                           
MODULE = Intersys::PERLBIND      PACKAGE = PDATE_STRUCTPtr

PDATE_STRUCT *
new(void)
PREINIT:
 PDATE_STRUCT * pstruct;
CODE:
{
    Newx( pstruct, 1, PDATE_STRUCT);
    RETVAL = pstruct;
}
OUTPUT:
    RETVAL

void 
DESTROY(pstruct)
   PDATE_STRUCT * pstruct
CODE:
{
    return;
}

int get_year(pdate)
PDATE_STRUCT * pdate;
CODE:
{
    RETVAL = pdate->year;
}
OUTPUT:
  RETVAL

int get_month(pdate)
PDATE_STRUCT * pdate;
CODE:
{
    RETVAL = pdate->month;
}
OUTPUT:
  RETVAL

int get_day(pdate)
PDATE_STRUCT * pdate;
CODE:
{
    RETVAL = pdate->day;
}
OUTPUT:
  RETVAL

void
set_year(pdate,val)
PDATE_STRUCT *pdate
int val
CODE:
{
    pdate->year = val;
}

void 
set_month(pdate,val)
PDATE_STRUCT *pdate
int val
CODE:
{
    pdate->month = val;
}

void 
set_day(pdate,val)
PDATE_STRUCT *pdate
int val
CODE:
{
    pdate->day = val;
}

char *toString(ptime)
PDATE_STRUCT *ptime;
PREINIT:
  char res[80];
CODE:
{
    sprintf(res,"%d-%2.2d-%2.2d", ptime->year, ptime->month, ptime->day);
    RETVAL=res;
}
OUTPUT:
  RETVAL


MODULE = Intersys::PERLBIND      PACKAGE = PTIME_STRUCTPtr

PTIME_STRUCT *
new(void)
PREINIT:
 PTIME_STRUCT * pstruct;
CODE:
{
    Newx( pstruct, 1, PTIME_STRUCT);
    RETVAL = pstruct;
}
OUTPUT:
    RETVAL

MODULE = Intersys::PERLBIND      PACKAGE = PTIME_STRUCTPtr
void 
DESTROY(pstruct)
   PTIME_STRUCT* pstruct
CODE:
{
    return;
}

int get_hour(ptime)
PTIME_STRUCT * ptime
CODE:
{
    RETVAL = ptime->hour;
}
OUTPUT:
  RETVAL

int get_minute(ptime)
PTIME_STRUCT * ptime
CODE:
{
    RETVAL = ptime->minute;
}
OUTPUT:
  RETVAL

int get_second(ptime)
PTIME_STRUCT * ptime
CODE:
{
    RETVAL = ptime->second;
}
OUTPUT:
  RETVAL

char *toString(ptime)
PTIME_STRUCT *ptime;
PREINIT:
  char res[80];
CODE:
{
    sprintf(res,"%2.2d:%2.2d:%2.2d", ptime->hour, ptime->minute, ptime->second);
    RETVAL=res;
}
OUTPUT:
  RETVAL

void 
set_hour(ptime,val)
PTIME_STRUCT * ptime
int val
CODE:
{
    if (val < 0 || val > 23) {
        Perl_croak(aTHX_ "invalid hour");
        return;
    }
    ptime->hour = val;
}

void 
set_minute(ptime, val)
PTIME_STRUCT* ptime
int val
CODE:
{
    if (val < 0 || val > 59) {
        Perl_croak(aTHX_ "invalid minute");
        return;
    }
    
    ptime->minute = val;
}

void 
set_second(ptime, val)
PTIME_STRUCT* ptime
int val
CODE:
{
    if (val < 0 || val > 59) {
        Perl_croak(aTHX_ "invalid second");
        return;
    }
    
    ptime->second = val;
}

MODULE = Intersys::PERLBIND      PACKAGE = PTIMESTAMP_STRUCTPtr

PTIMESTAMP_STRUCT *
new(void)
PREINIT:
 PTIMESTAMP_STRUCT * pstruct;
CODE:
{
    Newz(0, pstruct, 1, PTIMESTAMP_STRUCT);
    RETVAL = pstruct;
}
OUTPUT:
    RETVAL

void 
DESTROY(pstruct)
   PTIMESTAMP_STRUCT *pstruct
CODE:
{
    return;
}


int get_year(ptimestamp) 
PTIMESTAMP_STRUCT * ptimestamp
CODE: 
{ 
    RETVAL = ptimestamp->year; 
}
OUTPUT: 
  RETVAL

int get_month(ptimestamp)
PTIMESTAMP_STRUCT * ptimestamp;
CODE:
{
    RETVAL = ptimestamp->month;
}
OUTPUT:
  RETVAL

int get_day(ptimestamp)
PTIMESTAMP_STRUCT * ptimestamp;
CODE:
{
    RETVAL = ptimestamp->day;
}
OUTPUT:
  RETVAL

char *toString(ptime)
PTIMESTAMP_STRUCT *ptime;
PREINIT:
  char res[80];
CODE:
  {
    sprintf(res,"%d-%2.2d-%2.2d %2.2d:%2.2d:%2.2d.%d", ptime->year, ptime->month, ptime->day, ptime->hour, ptime->minute, ptime->second, ptime->fraction);
    RETVAL=res;
}
OUTPUT:
  RETVAL

void 
set_year(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    ptimestamp->year = val;
}

void 
set_month(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    ptimestamp->month = val;
}

void 
set_day(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    ptimestamp->day = val;
}

int get_hour(ptimestamp)
PTIMESTAMP_STRUCT * ptimestamp
CODE:
{
    RETVAL = ptimestamp->hour;
}
OUTPUT:
  RETVAL

int get_minute(ptimestamp)
PTIMESTAMP_STRUCT * ptimestamp
CODE:
{
    RETVAL = ptimestamp->minute;
}
OUTPUT:
  RETVAL

int get_second(ptimestamp)
PTIMESTAMP_STRUCT * ptimestamp
CODE:
{
    RETVAL = ptimestamp->second;
}
OUTPUT:
  RETVAL

int get_fraction(ptimestamp)
PTIMESTAMP_STRUCT * ptimestamp
CODE:
{
    RETVAL = ptimestamp->fraction;
}
OUTPUT:
  RETVAL

void 
set_hour(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    if (val < 0 || val > 23) {
        Perl_croak(aTHX_ "invalid hour");
        return;
    }
    
    ptimestamp->hour = val;
}

void 
set_minute(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    if (val < 0 || val > 59) {
        Perl_croak(aTHX_ "invalid minute");
        return;
    }
    
    ptimestamp->minute = val;
}

void 
set_second(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    if (val < 0 || val > 59) {
        Perl_croak(aTHX_ "invalid second");
        return;
    }

    
    ptimestamp->second = val;
}

void 
set_fraction(ptimestamp,val)
PTIMESTAMP_STRUCT *ptimestamp
int val
CODE:
{
    if (val < 0 || val > 999999999) {
        Perl_croak(aTHX_ "invalid fraction = %d, either less than 0 or greater than 999999999", val);
        return;
    }
        
    ptimestamp->fraction = val;
}



MODULE = Intersys::PERLBIND      PACKAGE = h_query
         
void
DESTROY(query)
  h_database query;
CODE:
{
    DEBUG_DESTROY("destroying query\n");
    RUN(cbind_query_close( query ));
    RUN(cbind_free_query( query ));
}

MODULE = Intersys::PERLBIND     PACKAGE = Intersys::PERLBIND::Query

void 
DESTROY(queryrv)
SV *queryrv
PREINIT:
SV *dbhashsv;
Query *my_query;
CODE:
{
    //warn("entering query destruction routine queryrv=%x
    //refcnt=%d\n",queryrv,SvREFCNT(queryrv));
    DEBUG_DESTROY1("in destroy query queryrv=%x\n", SvRV(queryrv));
    if (!SvROK(queryrv)) {
        INVALID_QUERY_WARNING("query cannot be destroyed: is not a reference\n");
        return;
    }
    my_query = get_query(queryrv);
    if (my_query == NULL) {
        INVALID_OBJ_WARNING1("cannot destroy var, it is NULL on query %x\n", queryrv);
    } else {
        destroy_query(my_query);
    }
    if (*(my_query->database_being_destroyed) == 1) return;    
    dbhashsv = my_query->_database;
    if (dbhashsv != NULL) {
        Query *query;
        int refcnt;

        if (!SvOK(dbhashsv)) {
            INVALID_QUERY_WARNING("dbhashrv is not defined in query destruction");
            return;
        }
        DEBUG_MEM("decrementing refcount of database refcount=%d\n", SvREFCNT(dbhashsv));        
        refcnt = SvREFCNT(dbhashsv);
        if (refcnt > 0) {
            query = get_query(queryrv);
            if (query != NULL) {
                remove_query_from_database(dbhashsv, query);
                DEBUG_MEM("decrementing database for query=%x\n",dbhashsv);
                SvREFCNT_dec(dbhashsv);                
            } else {
                INVALID_OBJ_WARNING("cannot remove query from database because is NULL\n");
            }
        }
        
    } else {
        INVALID_QUERY_WARNING("dbhashrv is NULL!\n");
    }
    // search for object on datbase list and remove it
    //warn("leaving object routine objectrv=%x\n",objectrv);
}

int
prepare(query_rv, sql_query, sql_code)
  SV* query_rv;
  char *sql_query
  int &sql_code
PREINIT:
  wchar_t w_sql_query[MAX_BUF];
  int unisize;
  wchar_t *p_unistr;
  h_query query;
  Mem_Ptr mem_stack[MAX_BUF];
  void *p_tos;
  int len;
CODE:
  {
	  p_tos = mem_stack;
      len = (int)strlen(sql_query);
      unisize = get_size_utf8_to_uni(sql_query, len);      
	  unisize = len;
      if (len > 0 && unisize==0) Perl_croak(aTHX_ "file=%s line=%d, Bad UTF8 string\n", __FILE__, __LINE__);      
	  unisize++;
      if (unisize < sizeof(w_sql_query)/sizeof(wchar_t)) {
		  p_unistr = w_sql_query;
      } else {
          Perl_croak(aTHX_ "file=%s line=%d, query too long\n", __FILE__, __LINE__);      
	  }
      cbind_utf8_to_uni(sql_query, len, p_unistr, sizeof(wchar_t)*unisize, &unisize);
      p_unistr[unisize] = 0;

    query = get_query_handle(query_rv);
    RUN(cbind_prepare_gen_query(query, p_unistr, &sql_code));
    //Safefree(w_sql_query);
    RETVAL=0;
}
OUTPUT:
    RETVAL
    sql_code

int
prepare_class(query_rv, cl_name, proc_name, sql_code)
  SV* query_rv
  char *cl_name
  char *proc_name
  int &sql_code
PREINIT:
  wchar_t w_cl_name[MAX_CLASS_NAME];
  wchar_t w_proc_name[MAX_PROC_NAME];
  int size;
  h_query query;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_mb_to_uni(cl_name, (byte_size_t)strlen(cl_name), NULL, 0,&size));
    //warn("size=%d\n",size);    
    //Newx( w_cl_name, size+1, wchar_t);
    RUN(cbind_mb_to_uni(cl_name, (byte_size_t)strlen(cl_name), w_cl_name, (char_size_t)size,&size));
    //warn("size=%d\n",size);
    w_cl_name[size] = 0;
    RUN(cbind_mb_to_uni(proc_name, (byte_size_t)strlen(proc_name), NULL, 0,&size));
    //warn("size=%d\n",size);    
    //Newx( w_proc_name, size+1, wchar_t);
    RUN(cbind_mb_to_uni(proc_name, (byte_size_t)strlen(proc_name), w_proc_name, (char_size_t)size,&size));
    //warn("size=%d\n",size);
    w_proc_name[size] = 0;
    
    RUN(cbind_prepare_class_query(query, w_cl_name, w_proc_name, &sql_code));
    //Safefree(w_cl_name);
    //Safefree(w_proc_name);
    RETVAL=0;
}
OUTPUT:
    RETVAL
    sql_code

int
execute(query_rv, sql_code)
  SV *query_rv
  int &sql_code
PREINIT:
  h_query query;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_execute(query, &sql_code));
    RETVAL=0;
}
OUTPUT:
    sql_code
    RETVAL

int
fetch(query_rv, sql_code)
  SV *query_rv
  int &sql_code
PREINIT:
    h_query query;
    int n;
    int i;
    SV **svarray;
    SV *sv;
    U32 context;
    Mem_Ptr mem_stack[MEM_STACK_SIZE];
    int tos = 0;
PPCODE:
{
    query = get_query_handle(query_rv);
    context = GIMME_V;
    RUN(cbind_query_fetch(query,&sql_code));
    sv_setiv(ST(1),sql_code);
    if (sql_code == 0) {
        RUN(cbind_query_get_num_cols(query, &n));
        if (context == G_ARRAY) {
            Newx( svarray, n, SV*);
            push_mem_stack(mem_stack, &tos, svarray, MEM_VOID);
            for (i = 0; i < n; i++) {
                sv = newSV(0);
                query_get_data(query,sv,i+1, mem_stack, &tos);
                svarray[i] = sv;
            }
            for (i=0; i < n; i++) {
                PUSHs(sv_2mortal(svarray[i]));
            }
            Safefree(svarray);
        } else {
            //warn("in scalar context n=%d\n",n);
            PUSHs(sv_2mortal(newSViv(n)));
        }
    } else {
        //warn("done\n");
    }
    RETVAL = 0;
}


int 
num_cols(query_rv)
  SV *query_rv
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_num_cols(query, &res));
    RETVAL=res;
}
OUTPUT:
  RETVAL

int 
col_sql_type(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_col_sql_type(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

SV*
col_name(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  const wchar_t * res;
  int utf8size;
  char utf8str[MAX_BUF];
  char *p_utf8str;
  int unisize;
  SV *sv;
  Mem_Ptr mem_stack[MEM_STACK_SIZE];
  int tos = 0;
  int *p_tos = &tos;
  int num_cols;
CODE:
{
    query = get_query_handle(query_rv);
    if (idx <= 0) {
        Perl_croak(aTHX_ "bad column number passed to col_name: %d file=%s line=%d\n", idx, __FILE__, __LINE__);
    }
    RUN(cbind_query_get_num_cols(query, &num_cols));
    if (idx > num_cols) {
        Perl_croak(aTHX_ "Column number %d > number of columns %d file=%s line=%d\n", idx, num_cols, __FILE__, __LINE__);
    }
    RUN(cbind_query_get_col_name(query, idx, &res));
    unisize = (int)wcslen(res);
    utf8size = get_size_uni_to_utf8((wchar_t*)res, unisize);
    if (utf8size+1 < sizeof(utf8str))
        p_utf8str = utf8str;
    else {
        Newx( p_utf8str, utf8size+1, char);
        push_mem_stack(mem_stack, p_tos, p_utf8str, MEM_VOID);

    }

    RUN(cbind_uni_to_utf8((wchar_t*)res, unisize, p_utf8str, utf8size, &utf8size));
    //p_utf8str[utf8size] = 0;
    sv = newSV(0);
    sv_setpvn(sv, p_utf8str, utf8size);
    SvUTF8_on(sv);
    if (utf8size +1 >= sizeof(utf8str)) {
        Safefree(p_utf8str);
        pop_mem_stack(p_tos);
    }
    RETVAL = sv;
}
OUTPUT:
  RETVAL

int
col_name_length(query_rv, idx)
  SV *query_rv
  int idx;
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_col_name_len(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

int
set_par(query_rv, idx, sv)
  SV *query_rv
  int idx
  SV *sv
PREINIT:
  h_query query;
  Mem_Ptr mem_stack[MAX_BUF];
  int tos = 0;
CODE:
{
    query = get_query_handle(query_rv);
    query_set_par(query, sv, idx, mem_stack, &tos);
    RETVAL = 0;
}
OUTPUT:
  RETVAL

int
num_pars(query_rv)
  SV *query_rv
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_num_pars(query, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

int
par_sql_type(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_par_sql_type(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

int
par_col_size(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_par_col_size(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

int
par_num_dec_digits(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  int res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_get_par_num_dec_digits(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

int
is_par_nullable(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  unsigned short res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_is_par_nullable(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL

int
is_par_unbound(query_rv, idx)
  SV *query_rv
  int idx
PREINIT:
  h_query query;
  bool_t res;
CODE:
{
    query = get_query_handle(query_rv);
    RUN(cbind_query_is_par_unbound(query, idx, &res));
    RETVAL = res;
}
OUTPUT:
  RETVAL
          
