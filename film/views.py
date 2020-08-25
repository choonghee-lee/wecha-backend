from collections import Counter

from django.views     import View
from django.http      import JsonResponse
from django.db.models import Count

from .models import (
    Film,
    Country,
    ServiceProvider,
    FilmURL,
    Person,
    Cast,
    Genre,
    FilmGenre,
    FilmCountry,
)
from user.models import (
    Collection,
    Review,
    User,
    FilmCollection,
)
from user.utils import token_authorization

class FilmRankingView(View):
    # 서비스 제공자에 따라 평균 별점이 높은 n개의 영화를 리턴한다.
    def get(self, request):
        service_provider_name = request.GET.get('sp', None)
        limit                 = request.GET.get('limit', 10)
        
        if ServiceProvider.objects.filter(name = service_provider_name).exists():
            service_provider = ServiceProvider.objects.get(name = service_provider_name)
            films = service_provider.film_set.order_by('-avg_rating')[:limit]
            
            body = {
                "films": [
                    {
                        "id"               : f.id,
                        "title"            : f.korean_title,
                        "year"             : f.release_date.year,
                        "avg_rating"       : f.avg_rating,
                        "poster_url"       : f.poster_url,
                        "countries"        : [ c['name'] for c in f.country.values()],
                        "service_providers": [ s['name'] for s in f.service_provider.values()]
                    }
                    for f in films
                ]
            }
            return JsonResponse(body, status = 200)

        return JsonResponse(
            {"message": "INVALID_QUERY_PARAMETER_SERVICE_PROVIDER"},
            status = 400
        )

class FilmDetailView(View):
    @token_authorization
    def get(self, request, film_id):        
        if Film.objects.filter(pk = film_id).exists():
            film = Film.objects.get(pk = film_id)

            body = {
                "id"                 : film.id,
                "korean_title"       : film.korean_title,
                "original_title"     : film.original_title,
                "year"               : film.release_date.year,
                "running_time_hour"  : film.running_time.hour,
                "running_time_minute": film.running_time.minute,
                "description"        : film.description,
                "poster_url"         : film.poster_url,
                "avg_rating"         : film.avg_rating,
                "countries"          : [c['name'] for c in film.country.values()],
                "genres"             : [g['name'] for g in film.genre.values()],
                "service_providers"  : [sp['name'] for sp in film.service_provider.values()],
                "film_urls"          : [
                    {
                        "id"           : fu.id,
                        "film_url_type": fu.film_url_type.name,
                        "film_url"     : fu.url
                    }  
                    for fu in film.filmurl_set.all().select_related('film_url_type')
                ],
                "casts" : [
                    {
                        "id"      : c.id,
                        "name"    : c.person.name,
                        "role"    : c.role,
                        "face_url": c.person.face_image_url
                    }  
                    for c in film.cast_set.all().select_related('person')
                ],
                "collections" : [
                    {
                        "id"         : c.id,
                        "name"       : c.name,
                        "user_id"    : c.user.id,
                        "poster_urls": [ f.poster_url for f in c.film.all()[:4] ]
                    }  
                    for c in film.collection_set.all().prefetch_related('film', 'user')
                ],
                "reviews" : [
                    {
                        "id"                 : r.id,
                        "comment"            : r.comment,
                        "like_count"         : r.like_count,
                        "score"              : r.score,
                        "user_id"            : r.user.id,
                        "user_face_image_url": r.user.face_image_url
                    }
                    for r in film.review_set.all().select_related('user').exclude(score__isnull=True)
                ],
                "score_counts" : [
                    score
                    for score in film.review_set.values('score').annotate(total=Count('score')).order_by('total')
                ],
            }
            
            # 로그인된 유저가 요청한 영화에 대한 리뷰가 있으면 body 추가해준다.
            if request.user:
                review = film.review_set.filter(film=film, user=request.user).exclude(score__isnull=True).select_related('user')
                if review.exists():
                    review = review.first()
                    body["authenticated_user_review"] = {
                        "id"                 : review.id,
                        "comment"            : review.comment,
                        "id"                 : review.pk,
                        "comment"            : review.comment,
                        "user_id"            : review.user.id,
                        "user_face_image_url": review.user.face_image_url
                    }

            return JsonResponse(body, status = 200)

        return JsonResponse(
            {"message": "INVALID_PATH_VARIABLE_FILM_ID"},
            status = 400
        )

class FilmRecommendationView(View):
    @token_authorization
    def get(self, request):
        way   = request.GET.get('way', None)
        limit = request.GET.get('limit', 18)

        if way == 'genre':
            if request.user:
                most_genre =  Counter([
                    g.name 
                    for r in request.user.review_set.select_related('film') 
                    for g in r.film.genre.all()
                ]).most_common(1)[0]
                film_queryset = Genre.objects.get(name = most_genre[0]).film_set.all().prefetch_related('country', 'service_provider')[:limit]
                
                body = {
                    "genre_name": most_genre[0],
                    "films": [
                        {
                            "id"        : f.id,
                            "title"     : f.korean_title,
                            "year"      : f.release_date.year,
                            "avg_rating": f.avg_rating,
                            "poster_url": f.poster_url,
                            "countries" : [
                                {
                                    "id"  : c['id'],
                                    "name": c['name']
                                }
                                for c in f.country.values()
                            ],
                            "service_providers": [
                                {
                                    "id"  : sp['id'],
                                    "name": sp['name']
                                }                            
                                for sp in f.service_provider.values()
                            ]
                        }
                        for f in film_queryset
                    ]
                }
                return JsonResponse(body, status=200)
            

        if way == 'country':
            if request.user:
                most_country =  Counter([
                    g.name 
                    for r in request.user.review_set.select_related('film') 
                    for g in r.film.country.all()
                ]).most_common(1)[0]
                film_queryset = Country.objects.get(name = most_country[0]).film_set.all().prefetch_related('country', 'service_provider')[:limit]
                
                body = {
                    "country_name": most_country[0],
                    "films": [
                        {
                            "id"       : f.id,
                            "title"    : f.korean_title,
                            "countries": [ 
                                {
                                    "id"  : c['id'],
                                    "name": c['name']
                                }
                                for c in f.country.values()
                            ],
                            "year"             : f.release_date.year,
                            "avg_rating"       : f.avg_rating,
                            "poster_url"       : f.poster_url,
                            "service_providers": [
                                {
                                    "id"  : sp['id'],
                                    "name": sp['name']
                                }                            
                                for sp in f.service_provider.values()
                            ]
                        }
                        for f in film_queryset
                    ]
                }
                return JsonResponse(body, status=200)

        if way == 'person':
            if request.user:
                most_person =  Counter([
                    g.name 
                    for r in request.user.review_set.select_related('film') 
                    for g in r.film.person.all()
                ]).most_common(1)[0]
                film_queryset = Person.objects.get(name = most_person[0]).film_set.all().prefetch_related('country', 'service_provider')[:limit]
                
                body = {
                    "person_name": most_person[0],
                    "films": [
                        {
                            "id"       : f.id,
                            "title"    : f.korean_title,
                            "countries": [ 
                                {
                                    "id"  : c['id'],
                                    "name": c['name']
                                }
                                for c in f.country.values()
                            ],
                            "year"             : f.release_date.year,
                            "avg_rating"       : f.avg_rating,
                            "poster_url"       : f.poster_url,
                            "service_providers": [
                                {
                                    "id"  : sp['id'],
                                    "name": sp['name']
                                }                            
                                for sp in f.service_provider.values()
                            ]
                        }
                        for f in film_queryset
                    ]
                }
                return JsonResponse(body, status=200)

        return JsonResponse(
            {"message": "INVALID_QUERY_PARAMETER_WAY"},
            status = 400
        )

class FilmCollectionListView(View):
    def get(self, request):
        limit       = request.GET.get('limit', 18)
        collections = Collection.objects.all().prefetch_related('film').order_by('?')[:limit]
        
        body = {
            "collections": [
                {
                    "id"        : c.id,
                    "name"      : c.name,
                    "poster_urls": [
                        f.poster_url
                        for f in c.film.all()[:4]
                    ] 
                }
                for c in collections
            ]
        }
        return JsonResponse(body, status = 200)

class FilmSearchView(View):
    def get(self, request):
        term  = request.GET.get('term', None)
        limit = request.GET.get('limit', 9)

        if term:
            body = {
                "results": [
                    {
                        "id"          : f.id,
                        "korean_title": f.korean_title
                    }
                    for f in Film.objects.filter(korean_title__icontains = term)[:limit]
                ]
            }
            return JsonResponse(body, status = 200)

        return JsonResponse(
            {"message": "INVALID_QUERY_PARAMETER_TERM"},
            status = 400
        ) 