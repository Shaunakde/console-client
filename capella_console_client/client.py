import logging

from datetime import datetime
from typing import List, Dict, Any, Union, Optional, no_type_check
from collections import defaultdict
from pathlib import Path
import tempfile

import dateutil.parser  # type: ignore

from capella_console_client.config import CONSOLE_API_URL
from capella_console_client.session import CapellaConsoleSession
from capella_console_client.logconf import logger
from capella_console_client.exceptions import (
    CapellaConsoleClientError,
    AuthenticationError,
    InsufficientFundsError,
    OrderRejectedError,
    NoValidStacIdsError,
    TaskNotCompleteError,
)

from capella_console_client.assets import (
    _perform_download,
    DownloadRequest,
    _gather_download_requests,
    _get_asset_bytesize,
    _derive_stac_id,
)
from capella_console_client.search import _build_search_payload, _paginated_search
from capella_console_client.validate import (
    _validate_uuid,
    _validate_stac_id_or_stac_items,
)


class CapellaConsoleClient:
    """
    API client for https://api.capellaspace.com.

    API docs: https://docs.capellaspace.com/accessing-data/searching-for-data

    Args:
        email: email on api.capellaspace.com
        password: password on api.capellaspace.com
        token: valid JWT access token
        verbose: flag to enable verbose logging
        no_token_check: does not check if provided JWT token is valid

    Note:

    * provide either email and password or a valid jwt token for authentication

    NOTE: Precedence order (high to low)
        1. email and password
        2. JWT token
    """

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        verbose: bool = False,
        no_token_check: bool = False,
        base_url: Optional[str] = CONSOLE_API_URL,
    ):

        self.verbose = verbose
        logger.setLevel(logging.WARNING)
        if verbose:
            logger.setLevel(logging.INFO)

        self._sesh = CapellaConsoleSession(base_url=base_url, verbose=verbose)
        self._sesh.authenticate(email, password, token, no_token_check)

    # USER
    def whoami(self) -> Dict[str, Any]:
        """
        display user info

        Returns:
            Dict[str, Any]: return of GET /user
        """
        with self._sesh as session:
            resp = session.get("/user")
        return resp.json()

    # TASKING
    def get_task(self, tasking_request_id: str) -> Dict[str, Any]:
        """
        fetch task for the specified `tasking_request_id`

        Args:
            tasking_request_id: tasking request UUID

        Returns:
            Dict[str, Any]: task metadata
        """
        with self._sesh as session:
            task_response = session.get(f"/task/{tasking_request_id}")

        return task_response.json()

    def is_task_completed(self, task: Dict[str, Any]) -> bool:
        """
        check if a task has completed
        """
        all_statuses = (s["code"] for s in task["properties"]["statusHistory"])
        return "completed" in all_statuses

    def get_collects_for_task(self, tasking_request_id: str) -> List[Dict[str, Any]]:
        """
        get all the collects associated with this task (see :py:meth:`get_task()`)

        Args:
            task: task metadata - return of :py:meth:`get_task()`

        Returns:
            List[Dict[str, Any]]: collect metadata associated
        """
        task = self.get_task(tasking_request_id)
        tasking_request_id = task["properties"]["taskingrequestId"]
        if not self.is_task_completed(task):
            raise TaskNotCompleteError(
                f"TaskingRequest<{tasking_request_id}> is not in completed state"
            )

        with self._sesh as session:
            collects_list_resp = session.get(f"/collects/list/{tasking_request_id}")

        return collects_list_resp.json()

    # ORDER
    def list_orders(
        self, *order_ids: Optional[str], is_active: Optional[bool] = False
    ) -> List[Dict[str, Any]]:
        """
        list orders

        Args:
            order_id: list only specific orders (variadic, specify multiple)
            is_active: list only active (non-expired) orders

        Returns:
            List[Dict[str, Any]]: metadata of orders
        """
        orders = []

        if order_ids:
            for order_id in order_ids:
                _validate_uuid(order_id)

        # prefilter non expired
        if is_active:
            orders = _get_non_expired_orders(session=self._sesh)
            if order_ids:
                set_order_ids = set(order_ids)
                orders = [o for o in orders if o["orderId"] in set_order_ids]
        else:
            # list all orders
            if not order_ids:
                with self._sesh as session:
                    params = {
                        "customerId": self._sesh.customer_id,
                    }
                    resp = session.get("/orders", params=params)
                orders = resp.json()

            # list specific orders
            else:
                with self._sesh as session:
                    for order_id in order_ids:
                        resp = session.get(f"/orders/{order_id}")
                        orders.append(resp.json())

        return orders

    def get_stac_items_of_order(
        self, order_id: str, ids_only: bool = False
    ) -> Union[List[str], List[Dict[str, Any]]]:
        """
        get stac items of an existing order

        Args:
            order_id: order id
        """
        _validate_uuid(order_id)
        order_meta = self.list_orders(order_id)[0]

        stac_ids = [item["granuleId"] for item in order_meta["items"]]
        if ids_only:
            return stac_ids

        return self.search(ids=stac_ids)

    def review_order(
        self,
        stac_ids: Optional[List[str]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        stac_ids = _validate_stac_id_or_stac_items(stac_ids, items)

        logger.info(f"reviewing order for {', '.join(stac_ids)}")

        stac_items = items  # type: ignore
        if not items:
            stac_items = self.search(ids=stac_ids)

        if not stac_items:
            raise NoValidStacIdsError(f"No valid STAC IDs in {', '.join(stac_ids)}")

        # review order
        order_payload = self._construct_order_payload(stac_items)
        with self._sesh as session:
            review_order_response = session.post(
                "/orders/review", json=order_payload
            ).json()

        if not review_order_response.get("authorized", False):
            raise InsufficientFundsError(
                review_order_response["authorizationDenialReason"]["message"]
            )

    def submit_order(
        self,
        stac_ids: Optional[List[str]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        check_active_orders: bool = False,
        omit_search: bool = False,
    ) -> str:
        """
        submit an order by `stac_ids` or `items`.

        NOTE: Precedence order (high to low)
            1. stac_ids
            2. items

        Args:
            stac_ids: STAC IDs that active order should include
            items: STAC items, returned by :py:meth:`search`
            check_active_orders: check if any active order containing ALL `stac_ids` is available
                if True: returns that order ID
                if False: submits a new order and returns new order ID
            omit_search: omit search to ensure provided STAC IDs are valid - only works if `items` are provided
            Returns:
                str: order UUID
        """
        stac_ids = _validate_stac_id_or_stac_items(stac_ids, items)

        if check_active_orders:
            order_id = self._find_active_order(stac_ids)
            if order_id is not None:
                logger.info(f"found active order {order_id}")
                return order_id

        logger.info(f"submitting order for {', '.join(stac_ids)}")
        if stac_ids and not omit_search:
            stac_items = self.search(ids=stac_ids)
        else:
            if omit_search and not items:
                logger.warning(
                    "setting omit_search=True only works in combination providing items instead of stac_ids"
                )
            stac_items = items  # type: ignore

        if not stac_items:
            raise NoValidStacIdsError(f"No valid STAC IDs in {', '.join(stac_ids)}")

        self.review_order(items=stac_items)

        order_payload = self._construct_order_payload(stac_items)

        # perform actual order
        with self._sesh as session:
            res_order = session.post("/orders", json=order_payload)

        con = res_order.json()
        order_id = con["orderId"]
        if con["orderStatus"] == "rejected":
            raise OrderRejectedError(f"Order for {', '.join(stac_ids)} rejected.")

        logger.info(f"successfully submitted order {order_id}")
        return order_id  # type: ignore

    def _construct_order_payload(self, stac_items):
        by_collect_id = defaultdict(list)
        for item in stac_items:
            by_collect_id[item["collection"]].append(item["id"])

        order_items = []
        for collection, stac_ids_of_coll in by_collect_id.items():
            order_items.extend(
                [
                    {"collectionId": collection, "granuleId": stac_id}
                    for stac_id in stac_ids_of_coll
                ]
            )
        return {"items": order_items}

    def _find_active_order(self, stac_ids: List[str]) -> Optional[str]:
        """
        find active order containing ALL specified `stac_ids`

        Args:
            stac_ids: STAC IDs that active order should include
        """

        if not stac_ids:
            raise ValueError("Please provide at least one stac_id")

        order_id = None
        active_orders = _get_non_expired_orders(session=self._sesh)
        if not active_orders:
            return None

        for ord in active_orders:
            granules = set([i["granuleId"] for i in ord["items"]])

            if granules.issuperset(stac_ids):
                order_id = ord["orderId"]
                logger.info(
                    f'all stac ids ({", ".join(stac_ids)}) found in active order {order_id}'
                )
                break
        return order_id

    def get_presigned_assets(
        self, order_id: str, stac_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        get presigned assets hrefs for all products contained in order

        Args:
            order_id: active order ID (see :py:meth:`submit_order`)
            stac_ids: filter presigned assets by STAC IDs

        Returns:
            List[Dict[str, Any]]: List of assets of respective product, e.g.

            .. highlight:: python
            .. code-block:: python

                [
                    {
                        "<asset_type>": {
                            "title": ...,
                            "href": ...,
                            "type": ...
                        },
                        ...
                    }
                ]

        """
        _validate_uuid(order_id)
        logger.info(f"getting presigned assets for order {order_id}")
        with self._sesh as session:
            res_dl = session.get(f"/orders/{order_id}/download")

        resp = res_dl.json()
        if not stac_ids:
            return [item["assets"] for item in resp]

        stac_ids_set = set(stac_ids)
        return [item["assets"] for item in resp if item["id"] in stac_ids_set]

    def get_asset_bytesize(self, pre_signed_url: str) -> int:
        """get size in bytes of `pre_signed_url`"""
        return _get_asset_bytesize(pre_signed_url)

    # DOWNLOAD
    def download_asset(
        self,
        pre_signed_url: str,
        local_path: Union[Path, str] = None,
        override: bool = False,
        show_progress: bool = False,
    ) -> Path:
        """
        downloads a presigned asset url to disk

        Args:
            pre_signed_url: presigned asset url, see :py:meth:`get_presigned_assets`
            local_path: local output path - file is written to OS's temp dir if not provided
            override: override already existing `local_path`
            show_progress: show download status progressbar
        """
        dl_request = DownloadRequest(
            url=pre_signed_url,
            local_path=local_path,  # type: ignore
            asset_key="asset",
        )
        return _perform_download(
            download_requests=[dl_request],
            override=override,
            threaded=False,
            verbose=self.verbose,
            show_progress=show_progress,
        )["asset"]

    def download_products(
        self,
        assets_presigned: Optional[List[Dict[str, Any]]] = None,
        order_id: Optional[str] = None,
        tasking_request_id: Optional[str] = None,
        collect_id: Optional[str] = None,
        local_dir: Union[Path, str] = Path(tempfile.gettempdir()),
        include: Union[List[str], str] = None,
        exclude: Union[List[str], str] = None,
        override: bool = False,
        threaded: bool = False,
        show_progress: bool = False,
        separate_dirs: bool = True,
    ) -> Dict[str, Dict[str, Path]]:
        """
        download all assets of multiple products

        Args:
            assets_presigned: mapping of presigned assets of multiple products, see :py:meth:`get_presigned_assets`
            order_id: optionally provide `order_id` instead of `assets_presigned`, see :py:meth:`submit_order`
            tasking_request_id: tasking request UUID of the task request you wish to download all associated products for
            collect_id: collect UUID you wish to download all associated products for

                    NOTE: Precedence order (high to low)
                      1. assets_presigned
                      2. order_id
                      3. tasking_request_id
                      4. collect_id

                    Meaning e.g. assets_presigned takes precedence over order_id, ...

            local_dir: local directory where assets are saved to, tempdir if not provided
            include: white-listing, which assets should be included, e.g. ["HH"] => only download HH asset
            exclude: black-listing, which assets should be excluded, e.g. ["HH", "thumbnail"] => download ALL except HH and thumbnail assets

                     NOTE: explicit DENY overrides explicit ALLOW

                     asset choices:
                        * 'HH', 'VV', 'raster', 'metadata', 'thumbnail' (external) - raster == 'HH' || 'VV'
                        * 'log', 'profile', 'stats', 'stats_plots' (internal)

            override: override already existing
            threaded: download assets of product in multiple threads
            show_progress: show download status progressbar
            separate_dirs: set to True in order to save the respective product assets into products directories, i.e.
                                /tmp/<stac_id_1>/<stac_id_1>.tif
                                /tmp/<stac_id_2>/<stac_id_2>.tif
                                ...
                            set to False in order to the respective product assets directly into the provided `local_dir`, i.e.
                               /tmp/<stac_id_1>.tif
                               /tmp/<stac_id_2>.tif
                               ...

        Returns:
            Dict[str, Dict[str, Path]]: Local paths of downloaded files keyed by STAC id and asset type, e.g.

            .. highlight:: python
            .. code-block:: python

                {
                    "stac_id_1": {
                        "<asset_type>": <path-to-asset>,
                        ...
                    }
                }
        """
        local_dir = Path(local_dir)

        one_of_equired = (assets_presigned, order_id, tasking_request_id, collect_id)

        if not any(map(bool, one_of_equired)):
            raise ValueError(
                "please provide one of assets_presigned, order_id, tasking_request_id or collect_id"
            )

        if not assets_presigned:
            assets_presigned = self._resolve_assets_presigned(
                order_id, tasking_request_id, collect_id
            )

        len_assets_presigned = len(assets_presigned)
        suffix = "s" if len_assets_presigned > 1 else ""
        logger.info(f"downloading {len_assets_presigned} product{suffix}")

        download_requests = []
        by_stac_id = {}

        # gather download requests
        for cur_assets in assets_presigned:
            cur_download_requests = _gather_download_requests(
                cur_assets, local_dir, include, exclude, separate_dirs
            )
            by_stac_id[cur_download_requests[0].stac_id] = {
                cur.asset_key: cur.local_path for cur in cur_download_requests
            }
            download_requests.extend(cur_download_requests)

        # download
        _perform_download(
            download_requests=download_requests,
            override=override,
            threaded=threaded,
            verbose=self.verbose,
            show_progress=show_progress,
        )
        return by_stac_id  # type: ignore

    def _resolve_assets_presigned(
        self,
        order_id: Optional[str] = None,
        tasking_request_id: Optional[str] = None,
        collect_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        # 1 - resolve assets_presigned from order_id
        if order_id:
            _validate_uuid(order_id)
        else:
            # 2 - submit order for tasking_request_id
            if tasking_request_id:
                _validate_uuid(tasking_request_id)
                order_id = self._order_products_for_task(tasking_request_id)  # type: ignore
            # 3 - submit order for collect_id
            else:
                _validate_uuid(collect_id)
                order_id = self._order_products_for_collect_ids(collect_ids=[collect_id])  # type: ignore

        return self.get_presigned_assets(order_id)  # type: ignore

    def _order_products_for_task(self, tasking_request_id: str) -> str:
        """
        order all products associated with a tasking request

        Args:
            tasking_request_id: tasking request UUID you wish to order all associated products for
        """
        # gather up all collect IDs associated of this task
        collect_ids = [
            coll["collectId"] for coll in self.get_collects_for_task(tasking_request_id)
        ]
        return self._order_products_for_collect_ids(collect_ids)

    def _order_products_for_collect_ids(self, collect_ids: List[str]) -> str:
        stac_items = self.search(collect_id__in=collect_ids)
        order_id = self.submit_order(items=stac_items, omit_search=True)
        return order_id

    def download_product(
        self,
        assets_presigned: Optional[Dict[str, Any]] = None,
        order_id: Optional[str] = None,
        local_dir: Union[Path, str] = Path(tempfile.gettempdir()),
        include: Union[List[str], str] = None,
        exclude: Union[List[str], str] = None,
        override: bool = False,
        threaded: bool = False,
        show_progress: bool = False,
    ) -> Dict[str, Path]:
        """
        download all assets of a product

        Args:
            assets_presigned: mapping of presigned assets of multiple products, see :py:meth:`get_presigned_assets`
            order_id: optionally provide `order_id` instead of `assets_presigned`, see :py:meth:`submit_order`

                NOTE: Precedence order (high to low)
                  1. assets_presigned
                  2. order_id

            local_dir: local directory where assets are saved to, tempdir if not provided
            include: white-listing, which assets should be included, e.g. ["HH"] => only download HH asset
            exclude: black-listing, which assets should be excluded, e.g. ["HH", "thumbnail"] => download ALL except HH and thumbnail assets
                     NOTE: explicit DENY overrides explicit ALLOW

                     asset choices:
                        * 'HH', 'VV', 'raster', 'metadata', 'thumbnail' (external)
                           Note: raster == 'HH' || 'VV'
                        * 'log', 'profile', 'stats', 'stats_plots' (internal accessible only)

            override: override already existing
            threaded: download assets of product in multiple threads
            show_progress: show download status progressbar

        Returns:
            Dict[str, Path]: Local paths of downloaded files keyed by asset type, e.g.

            .. highlight:: python
            .. code-block:: python

                {
                    "<asset_type>": <path-to-asset>,
                    ...
                }
        """
        if not assets_presigned and not order_id:
            raise ValueError("please provide either assets_presigned or order_id")

        if not assets_presigned:
            _validate_uuid(order_id)
            assets_presigned = self._get_first_presigned_from_order(order_id)

        download_requests = _gather_download_requests(assets_presigned, local_dir, include, exclude)  # type: ignore

        return _perform_download(
            download_requests=download_requests,
            override=override,
            threaded=threaded,
            verbose=self.verbose,
            show_progress=show_progress,
        )

    @no_type_check
    def _get_first_presigned_from_order(self, order_id: str) -> Dict[str, Any]:
        assets_presigned = self.get_presigned_assets(order_id)
        if len(assets_presigned) > 1:
            logger.warning(
                f"order {order_id} contains {len(assets_presigned)} products - using first one ({_derive_stac_id(assets_presigned)})"
            )

        return assets_presigned[0]

    # SEARCH
    def search(self, **kwargs) -> List[Dict[str, Any]]:
        """
        paginated search for up to 500 matches (if no bigger limit specified)

        Find more information at https://docs.capellaspace.com/accessing-data/searching-for-data

        supported search filters:

         • bbox: List[float, float, float, float], e.g. [12.35, 41.78, 12.61, 42]
         • billable_area: Billable Area in m^2
         • center_frequency: Union[int, float], Center Frequency (GHz)
         • collections: List[str], e.g. ["capella-open-data"]
         • collect_id: str, capella internal collect-uuid, e.g. '78616ccc-0436-4dc2-adc8-b0a1e316b095'
         • constellation: str, e.g. "capella"
         • datetime: str, e.g. "2020-02-12T00:00:00Z"
         • frequency_band: str, Frequency band, one of "P", "L", "S", "C", "X", "Ku", "K", "Ka"
         • ids: List[str], e.g. `["CAPELLA_C02_SP_GEO_HH_20201109060434_20201109060437"]`
         • intersects: geometry component of the GeoJSON, e.g. {'type': 'Point', 'coordinates': [-113.1, 51.1]}
         • incidence_angle: Union[int, float], Center incidence angle, between 0 and 90
         • instruments: List[str], leveraged instruments, e.g. ["capella-radar-5"]
         • instrument_mode: str, Instrument mode, one of "spotlight", "stripmap", "sliding_spotlight"
         • limit: int, default: 500
         • look_angle: Union[int, float], e.g. 28.4
         • looks_azimuth: int, e.g. 5
         • looks_equivalent_number: int, Equivalent number of looks (ENL), e.g. 3
         • looks_range: int, e.g. 5
         • observation_direction: str, Antenna pointing direction, one of "right", "left"
         • orbit_state: str, Orbit State, one of "ascending", "descending"
         • orbital_plane: int, Orbital Plane, inclination angle of orbit
         • pixel_spacing_azimuth: Union[int, float], Pixel spacing azimuth (m), e.g. 0.5
         • pixel_spacing_range: Union[int, float], Pixel spacing range (m), e.g. 0.5
         • platform: str, e.g. "capella-2"
         • polarizations: str, one of "HH", "VV", "HV", "VH"
         • product_category: str, one of "standard", "custom", "extended"
         • product_type: str, one of "SLC", "GEO"
         • resolution_azimuth: float, Resolution azimuth (m), e.g. 0.5
         • resolution_ground_range: float, Resolution ground range (m), e.g. 0.5
         • resolution_range: float, Resolution range (m), e.g. 0.5
         • squint_angle: float, Squint angle, e.g. 30.1

        supported operations:
         • eq: equality search
         • in: within group
         • gt: greater than
         • gte: greater than equal
         • lt: lower than
         • lte: lower than equal

        sorting:
        • sortby: List[str] - must be supported fields, e.g. ["+datetime"]

        Returns:
            List[Dict[str, Any]]: STAC items matched
        """
        payload = _build_search_payload(**kwargs)
        logger.info(f"searching catalog with payload {payload}")
        return _paginated_search(self._sesh, payload)


def _get_non_expired_orders(session: CapellaConsoleSession) -> List[Dict[str, Any]]:
    with session:
        params = {"customerId": session.customer_id}
        res = session.get("/orders", params=params)

    all_orders = res.json()

    ordered_by_exp_date = sorted(all_orders, key=lambda x: x["expirationDate"])
    now = datetime.utcnow()

    active_orders = []
    while ordered_by_exp_date:
        cur = ordered_by_exp_date.pop()
        cur_exp_date = dateutil.parser.parse(cur["expirationDate"], ignoretz=True)
        if cur_exp_date < now:
            break
        active_orders.append(cur)

    return active_orders