.. _example_usage:

**************
Example Usage
**************

authenticate
############

.. code:: python3

    from getpass import getpass
    from capella_console_client import CapellaConsoleClient

    # user credentials on console.capellaspace.com
    email = input("your email on console.capellaspace.com:").strip()
    pw = getpass("your password on console.capellaspace.com:").strip()

    # authenticate
    client = CapellaConsoleClient(email=email, password=pw)

    # chatty client
    client = CapellaConsoleClient(email=email, password=pw, verbose=True)

authentication options

.. code:: python3

    # already have a valid JWT token? no problem
    token_client = CapellaConsoleClient(token='<MOCK_TOKEN>', verbose=True)

    # don't want to validate the token (saves an API call)
    bold_token_client = CapellaConsoleClient(token='<MOCK_TOKEN>', no_token_check=True)


search
######

the following snippet shows common search operation

.. code:: python3

    # random capella product
    random_product = client.search(constellation="capella", limit=1)[0]

    # stack of products of same bounding box
    stack_by_bbox = client.search(
        bbox=random_product['bbox']
    )

    # spotlight
    capella_spotlight = client.search(
        constellation="capella", 
        instrument_mode="spotlight", 
        limit=1
    )[0]

    # capella spotlight GEO product over Olympic National Park, Washington State
    olympic_NP_bbox = [-122.4, 46.9, -124.9, 48.5]

    capella_spotlight_olympic_NP_geo = client.search(
        constellation="capella",
        instrument_mode="spotlight", 
        bbox=olympic_NP_bbox,
        product_type="GEO"
    )


By default up to **500** STAC items are returned. This can be increased by providing a custom limit:

.. code:: python3

    # random capella product
    many_products = client.search(constellation="capella", limit=1000)


search fields
##############

.. list-table:: Supported search fields
    :widths: 30 60 20 20
    :header-rows: 1

    * - field name
      - type
      - description
      - example
    * - bbox
      - bounding box
      - List[float, float, float, float]
      - [12.35, 41.78, 12.61, 42]
    * - billable_area
      - billable Area (m^2)
      - int
      - 100000000
    * - center_frequency: number,
      - center Frequency (GHz)
      - number (Union[int, float])
      - 9.65
    * - collections
      - STAC collections
      - List[str]
      - ["capella-open-data"]
    * - collect_id
      - capella internal collect-uuid
      - str
      - "78616ccc-0436-4dc2-adc8-b0a1e316b095"
    * - constellation
      - constellation identifier
      - str
      - "capella"
    * - datetime
      - mid time of collect in Zulu format
      - str
      - "2020-02-12T00:00:00Z"
    * - frequency_band
      - Frequency band, one of "P", "L", "S", "C", "X", "Ku", "K", "Ka"
      - str
      - "X"
    * - ids
      - STAC identifiers (unique product identifiers)
      - List[str]
      - ["CAPELLA_C02_SP_GEO_HH_20201109060434_20201109060437"]
    * - intersects
      - geometry component of GeoJSON
      - geometryGeoJSON
      - {'type': 'Point', 'coordinates': [-113.1, 51.1]}
    * - incidence_angle
      - center incidence angle, between 0 and 90
      - number
      - 31
    * - instruments
      - leveraged instruments
      - List[str]
      - ["capella-radar-5"]
    * - instrument_mode
      - instrument mode, one of "spotlight", "stripmap", "sliding_spotlight"
      - str
      - "spotlight"
    * - look_angle: number, e.g. 10
      - look angle
      - Union[int, float]
      - 28.4
    * - looks_azimuth
      - looks in azimuth
      - int
      - 7
    * - looks_equivalent_number
      - equivalent number of looks (ENL)
      - int
      - 7
    * - looks_range
      - looks in range
      - int
      - 1
    * - observation_direction
      - antenna pointing direction, one of "right", "left"
      - str
      - "left"
    * - orbit_state
      - orbit State, one of "ascending", "descending"
      - str
      - "ascending"
    * - orbital_plane
      - Orbital Plane, inclination angle of orbit, one of 45, 53, 97
      - int
      - 45
    * - pixel_spacing_azimuth
      - pixel spacing azimuth (m)
      - Union[int, float]
      - 5
    * - pixel_spacing_range
      - pixel spacing range (m)
      - Union[int, float]
      - 5
    * - platform
      - platform identifier
      - str
      - "capella-6"
    * - polarizations
      - polarization, one of "HH", "VV"
      - List[str]
      - ["HH"]
    * - product_category
      - product category, one of "standard", "custom", "extended"
      - str
      - "standard"
    * - product_type
      - product type str, one of "SLC", "GEO", "GEC", "SICD", "SIDD"
      - str
      - "SLC"
    * - resolution_azimuth
      - resolution azimuth (m)
      - float
      - 0.5
    * - resolution_ground_range
      - resolution ground range (m)
      - float
      - 0.5
    * - resolution_range
      - resolution range (m)
      - float
      - 0.5
    * - squint_angle
      - squint angle
      - float
      - 30.1


advanced search
###############

.. code:: python3

    # sorted search descending by datetime, collected on capella-5 with HH polarization
    vvs = client.search(
        polarizations='HH',
        platform='capella-5',
        sortby='-datetime'
    )

    # sorted search desc by datetime and 2nd ascending by (STAC) id
    vvs = client.search(
        polarizations='VV',
        platform='capella-2',
        sortby=['-datetime', '+id']
    ) 

    # get up to 10 SLC stripmap products collected in June of 2021 
    capella_sm_01_2021 = client.search(
        instrument_mode="stripmap",
        datetime__gt="2021-06-01T00:00:00Z",
        datetime__lt="2021-07-01T00:00:00Z",
        product_type="SLC",
        limit=10, 
    )

    # get up to 10 GEO stripmap or spotlight products 
    capella_sm_or_sp = client.search(
        instrument_mode__in=["stripmap", "spotlight"],
        product_type="GEO",
        limit=10, 
    )

    # get up to 10 products with azimuth resolution <= 0.5 AND range resolution between 0.3 and 0.5
    capella_sm_or_sp_hq = client.search(
        resolution_azimuth__lte=0.5,
        resolution_range__gte=0.3,
        resolution_range__lte=0.5,
        limit=10, 
    )

    # get up to 10 GEO sliding spotlight products with look angle > 35
    plus35_lookangle_sliding_spotlight = client.search(
        look_angle__gt=35,
        product_type="GEO",
        instrument_mode="sliding_spotlight",
        limit=10
    )

    # take it to the max 
    # get GEO spotlight products over San Francisco's downtown with many filters sorted by datetime

    sanfran_dt_bbox = [-122.4, 37.8, -122.3, 37.7]
    hefty_query_SF_sorted = client.search(
        bbox=sanfran_dt_bbox,
        datetime__gt="2021-05-01T00:00:00Z",
        datetime__lt="2021-07-01T00:00:00Z"
        instrument_mode="spotlight",
        product_type="GEO",
        look_angle__gt=25,
        look_angle__lt=35,
        looks_equivalent_number=9,
        polarizations=["HH"],
        resolution_azimuth__lte=1,
        resolution_range__lte=1,
        orbit_state="descending",
        orbital_plane=45,
        observation_direction="right",
        squint_angle__gt=-0.5,
        squint_angle__lt=0.5,
        sortby='-datetime',
        collections=["capella-geo"]
    )

`capella-console-client` supports the following search operators:

.. list-table:: Supported search operators
   :widths: 30 60
   :header-rows: 1

   * - operator
     - example
   * - eq
     - .. code:: python3

         product_type__eq="GEO" (== product_type="GEO")
   * - in
     - .. code:: python3
     
         product_type__in=["SLC", "GEO", "GEC"]
   * - gt
     - .. code:: python3
     
         datetime__gt="2021-01-01T00:00:00Z"
   * - lt
     - .. code:: python3
     
         datetime__lt="2021-02-01T00:00:00Z"
   * - gte
     - .. code:: python3
     
         resolution_range__gte=0.3
   * - lte
     - .. code:: python3
     
         resolution_azimuth__lte=0.5

The API for advanced filtering operations was inspired by `Django's ORM <https://docs.djangoproject.com/en/3.2/topics/db/queries/#chaining-filters>`_


order products
##############

.. code:: python3

    # submit order of previously search stac items
    order_id = client.submit_order(items=capella_spotlight_olympic_NP_geo)

    # alternatively order by STAC ids
    first_two_ids = [item['id'] for item in capella_spotlight_olympic_NP_geo[:2]]
    order_id = client.submit_order(stac_ids=first_two_ids)

    # alternatively check prior to ordering if an active order already exists
    order_id = client.submit_order(items=capella_spotlight_olympic_NP_geo,
                                   check_active_orders=True)


download multiple products
##########################

.. code:: python3

    # download all products of order to /tmp
    product_paths = client.download_products(
        order_id=order_id,
        local_dir='/tmp',
    )

    # 🕒 don't like waiting? 🕒 - set threaded = True in order to fetch the product assets in parallel
    product_paths = client.download_products(
        order_id=order_id,
        local_dir='/tmp',
        threaded=True
    )

    # ⌛ like to watch progress bars? ⌛ - set show_progress = True in order to get feedback on download status (time remaining, transfer stats, ...)
    product_paths = client.download_products(
        order_id=order_id,
        local_dir='/tmp',
        threaded=True,
        show_progress=True,
    )


Output
.. code:: console

    2021-06-21 20:28:16,734 - 🛰️  Capella Space 🐐 - INFO - downloading product CAPELLA_C03_SP_SLC_HH_20210621202423_20210621202425 to /tmp
    CAPELLA_C03_SP_GEO_HH_20210603175705_20210603175729_thumb.png       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100.0% • 211.3/211.3 KB   • 499.7 kB/s  • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210619045726_20210619045747_thumb.png       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100.0% • 307.1/307.1 KB   • 1.4 MB/s    • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210619180117_20210619180140_thumb.png       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100.0% • 271.6/271.6 KB   • 1.1 MB/s    • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210627180259_20210627180321_extended.json   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0.0%   • 20,426/-1 bytes  • 200.2 kB/s  • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210603175705_20210603175729_extended.json   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0.0%   • 21,536/-1 bytes  • 293.8 kB/s  • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210619180117_20210619180140_extended.json   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0.0%   • 20,650/-1 bytes  • 122.0 kB/s  • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210627180259_20210627180321_thumb.png       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100.0% • 316.7/316.7 KB   • 1.3 MB/s    • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210603175705_20210603175729.tif             ━╸━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.6%   • 13.2/237.4 MB    • 2.2 MB/s    • 0:01:42
    CAPELLA_C03_SP_GEO_HH_20210619045726_20210619045747_extended.json   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0.0%   • 22,002/-1 bytes  • 196.9 kB/s  • 0:00:00
    CAPELLA_C03_SP_GEO_HH_20210627180259_20210627180321.tif             ━╺━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.0%   • 11.0/360.9 MB    • 1.9 MB/s    • 0:03:04
    CAPELLA_C03_SP_GEO_HH_20210619045726_20210619045747.tif             ╸━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.7%   • 9.8/359.0 MB     • 1.8 MB/s    • 0:03:18



download all products of a tasking request
##########################################

Requirement: you have issued a tasking request that was completed in the meantime

.. code:: python3

    task_request_id = '27a71826-7819-48cc-b8f2-0ad10bee0f97'  # provide valid tasking_request_id
    
    product_paths = client.download_products(
        tasking_request_id=tasking_request_id,
        local_dir='/tmp',
        threaded=True,
        show_progress=True,
    )



download all products of a collect
##################################

.. code:: python3

    collect_id = '27a71826-7819-48cc-b8f2-0ad10bee0f97'  # provide valid collect_id
    
    product_paths = client.download_products(
        collect_id=collect_id,
        local_dir='/tmp',
        threaded=True,
        show_progress=True,
    )


presigned asset hrefs
#####################

.. code:: python3

    # get pressigned asset urls of that order
    assets_presigned = client.get_presigned_assets(order_id)

    # alternatively presigned assets can also be filtered - e.g. give me the presigned assets of 3 stac items within the order
    assets_presigned = client.get_presigned_assets(order_id,
                                                   stac_ids=first_two_ids)


download single product
#######################


.. code:: python3

    # download a specific product with download_product (SINGULAR)
    product_paths = client.download_product(assets_presigned[0], local_dir='/tmp', override=True)
    


download single asset
#####################

.. code:: python3
    
    # download thumbnail
    thumb_presigned_href = assets_presigned[0]['thumbnail']['href']
    dest_path = '/tmp/thumb.png'
    local_thumb_path = client.download_asset(thumb_presigned_href, local_path=dest_path)

    # assets are saved into OS specific temp directory if `local_path` not provided
    raster_presigned_href = assets_presigned[0]['HH']['href']
    local_raster_path = client.download_asset(raster_presigned_href)
    print(local_raster_path)
    from pathlib import Path
    assert local_thumb_path == Path(dest_path)

    # the client is respectful of your local files and does not override them by default ...
    local_thumb_path = client.download_asset(thumb_presigned_href, local_path=dest_path)

    # ... but can be instructed to do so
    local_thumb_path = client.download_asset(thumb_presigned_href, local_path=dest_path, override=True)



download with asset type filter
###############################

.. code:: python3

    # download only thumbnails
    product_paths = client.download_products(assets_presigned, include=["thumbnail"], local_dir='/tmp', threaded=True)

    # can also be a string if only one provided
    product_paths = client.download_products(assets_presigned, include="thumbnail", local_dir='/tmp', threaded=True)

    # download only raster (VV or HH)
    product_paths = client.download_products(assets_presigned, include=["raster"], local_dir='/tmp', threaded=True)

    # download all assets except HH
    product_paths = client.download_products(assets_presigned, exclude=["HH"], local_dir='/tmp', threaded=True)

    # explicit DENY overrides explicit ALLOW --> the following would only fetch all thumbnails
    product_paths = client.download_products(assets_presigned, include=["HH", "thumbnail"], exclude=["HH"], local_dir='/tmp', threaded=True)


list orders
##############

    # list all orders
    all_orders = client.list_orders()

    # list all active orders
    all_active_orders = client.list_orders(is_active=True)

    # list specific order(s) by order id 
    specific_order_id = all_orders[0]['orderId']
    specific_orders = client.list_orders(order_ids=[specific_order_id])


tasking requests
################

.. code:: python3

    task_request_id = '27a71826-7819-48cc-b8f2-0ad10bee0f97'  # provide valid tasking_request_id

    # get task info
    task = client.get_task(task_request_id)

    # was it completed ?
    client.is_task_completed(task)

    # given that task request id, download all associated products
    client.download_products_for_task(task_request_id, local_dir='/tmp', threaded=True)


read imagery
############

requires rasterio (not part of this package)

.. code:: python3

    import rasterio

    # read metadata
    raster_presigned_href = assets_presigned[0]['HH']['href']
    with rasterio.open(raster_presigned_href) as ds:
        print(ds.profile)

    # read chunk of full raster
    with rasterio.open(raster_presigned_href) as ds:
        chunk = ds.read(1, window=rasterio.windows.Window(2000, 2000, 7000, 7000)) 
    print(chunk.shape)
        
    # read thumbnail
    thumb_presigned_href = assets_presigned[0]['thumbnail']['href']
    with rasterio.open(thumb_presigned_href) as ds:
        thumb = ds.read(1)
    print(thumb.shape)
