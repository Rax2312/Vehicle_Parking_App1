from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from models.models import ParkingLot, ParkingSpot, User, Reservation, db
from sqlalchemy.orm import joinedload

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@login_required
def dashboard():
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    return render_template('admin_dashboard.html', admin=current_user)

@admin_bp.route('/admin/lots', methods=['GET', 'POST'])
@login_required
def lot_list():
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    if request.method == 'POST':
        # Add new lot
        name = request.form['prime_location_name']
        price = request.form['price']
        address = request.form['address']
        pin_code = request.form['pin_code']
        number_of_spots = int(request.form['number_of_spots'])
        lot = ParkingLot(
            prime_location_name=name,
            price=price,
            address=address,
            pin_code=pin_code,
            number_of_spots=number_of_spots
        )
        db.session.add(lot)
        db.session.commit()
        # Create number of spots
        from models.models import ParkingSpot
        for i in range(1, number_of_spots + 1):
            spot = ParkingSpot(lot_id=lot.id, spot_number=i, status='A', floor=1)
            db.session.add(spot)
        db.session.commit()
        flash('Parking lot and spots added successfully!', 'success')
        return redirect(url_for('admin.lot_list'))
    # checking if existing lots have the correct number of spots by filling any missing ones
    from models.models import ParkingSpot
    lots = ParkingLot.query.all()
    for lot in lots:
        existing_spot_numbers = {spot.spot_number for spot in ParkingSpot.query.filter_by(lot_id=lot.id).all()}
        for i in range(1, lot.number_of_spots + 1):
            if i not in existing_spot_numbers:
                spot = ParkingSpot(lot_id=lot.id, spot_number=i, status='A', floor=1)
                db.session.add(spot)
        # Count the currently occupied spots in each lot
        lot.occupied = ParkingSpot.query.filter_by(lot_id=lot.id, is_occupied=True).count()
    db.session.commit()
    return render_template('lot_list.html', lots=lots)

@admin_bp.route('/admin/lots/edit/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def edit_lot(lot_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method == 'POST':
        lot.prime_location_name = request.form['prime_location_name']
        lot.price = request.form['price']
        lot.address = request.form['address']
        lot.pin_code = request.form['pin_code']
        new_spots = int(request.form['number_of_spots'])
        old_spots = lot.number_of_spots
        lot.number_of_spots = new_spots
        db.session.commit()
        # Adjust ParkingSpot records
        from models.models import ParkingSpot
        current_spots = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.spot_number).all()
        if new_spots > old_spots:
            for i in range(old_spots+1, new_spots+1):
                spot = ParkingSpot(lot_id=lot.id, spot_number=i, status='A', floor=1)
                db.session.add(spot)
        elif new_spots < old_spots:
            for i in range(old_spots, new_spots, -1):
                spot = ParkingSpot.query.filter_by(lot_id=lot.id, spot_number=i).first()
                if spot and not spot.is_occupied:
                    db.session.delete(spot)
        db.session.commit()
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('admin.lot_list'))
    return render_template('lot_form.html', lot=lot)

@admin_bp.route('/admin/lots/delete/<int:lot_id>', methods=['POST'])
@login_required
def delete_lot(lot_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    lot = ParkingLot.query.get_or_404(lot_id)
    from models.models import ParkingSpot, Reservation
    # is_occupied=False for spots with no active reservation
    spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    for spot in spots:
        active_res = Reservation.query.filter_by(spot_id=spot.id, status='Active').first()
        if not active_res and spot.is_occupied:
            spot.is_occupied = False
    db.session.commit()
    occupied = ParkingSpot.query.filter_by(lot_id=lot.id, is_occupied=True).count()
    if occupied > 0:
        flash('Cannot delete lot: some spots are still occupied.', 'danger')
        return redirect(url_for('admin.lot_list'))
    db.session.delete(lot)
    db.session.commit()
    flash('Parking lot deleted successfully!', 'success')
    return redirect(url_for('admin.lot_list'))

@admin_bp.route('/admin/spots', methods=['GET', 'POST'])
@login_required
def spot_list():
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    lots = ParkingLot.query.options(joinedload(ParkingLot.spots)).all()
    spot_ids = [spot.id for lot in lots for spot in lot.spots]
    active_reservations = {r.spot_id for r in Reservation.query.filter(Reservation.spot_id.in_(spot_ids), Reservation.status == 'Active').all()}
    # dict of lot_id -> list of spot dicts for js
    spots_by_lot_id = {}
    for lot in lots:
        spots_serialized = []
        for spot in lot.spots:
            is_occupied = spot.id in active_reservations
            spots_serialized.append({
                'is_occupied': is_occupied,
                'spot_number': spot.spot_number,
                'id': spot.id,
                'floor': spot.floor,
                'status': spot.status
            })
        spots_by_lot_id[lot.id] = spots_serialized

    lots_serialized = [
        {
            'id': lot.id,
            'prime_location_name': lot.prime_location_name,
            'address': lot.address,
            'number_of_spots': lot.number_of_spots
        }
        for lot in lots
    ]
    if request.method == 'POST':
        lot_id = request.form['lot_id']
        spot_number = request.form['spot_number']
        floor = request.form.get('floor', 1)
        status = request.form.get('status', 'A')
        spot = ParkingSpot(lot_id=lot_id, spot_number=spot_number, floor=floor, status=status)
        db.session.add(spot)
        db.session.commit()
        flash('Parking spot added successfully!', 'success')
        return redirect(url_for('admin.spot_list'))
    return render_template('spot_list.html', lots=lots, spots_by_lot_id=spots_by_lot_id, lots_data=lots_serialized)

@admin_bp.route('/admin/spots/edit/<int:spot_id>', methods=['GET', 'POST'])
@login_required
def edit_spot(spot_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    spot = ParkingSpot.query.get_or_404(spot_id)
    lots = ParkingLot.query.all()
    if request.method == 'POST':
        spot.lot_id = request.form['lot_id']
        spot.spot_number = request.form['spot_number']
        spot.floor = request.form.get('floor', 1)
        spot.status = request.form.get('status', 'A')
        db.session.commit()
        flash('Parking spot updated successfully!', 'success')
        return redirect(url_for('admin.spot_list'))
    return render_template('spot_form.html', spot=spot, lots=lots)

@admin_bp.route('/admin/spots/delete/<int:spot_id>', methods=['POST'])
@login_required
def delete_spot(spot_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    spot = ParkingSpot.query.get_or_404(spot_id)
    db.session.delete(spot)
    db.session.commit()
    flash('Parking spot deleted successfully!', 'success')
    return redirect(url_for('admin.spot_list'))

@admin_bp.route('/admin/users')
@login_required
def user_list():
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    users = User.query.all()
    user_stats = {}
    for user in users:
        user_stats[user.id] = {
            'reservations': Reservation.query.filter_by(user_id=user.id).count(),
            'flagged': user.flagged
        }
    return render_template('user_list.html', users=users, user_stats=user_stats)

@admin_bp.route('/admin/users/flag/<int:user_id>', methods=['POST'])
@login_required
def flag_user(user_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    user = User.query.get_or_404(user_id)
    user.flagged = True
    db.session.commit()
    return '', 204

@admin_bp.route('/admin/users/unflag/<int:user_id>', methods=['POST'])
@login_required
def unflag_user(user_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    user = User.query.get_or_404(user_id)
    user.flagged = False
    db.session.commit()
    return '', 204

@admin_bp.route('/admin/users/history/<int:user_id>')
@login_required
def user_history(user_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    user = User.query.get_or_404(user_id)
    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_timestamp.desc()).all()
    from datetime import datetime
    reservation_list = []
    for r in reservations:
        lot = r.lot
        spot = r.spot
        now = datetime.now()
        if r.leaving_timestamp:
            duration_minutes = int((r.leaving_timestamp - r.parking_timestamp).total_seconds() // 60)
            hours_parked = round(duration_minutes / 60, 2)
            revenue = round(hours_parked * lot.price, 2) if lot else 0
        else:
            duration_minutes = int((now - r.parking_timestamp).total_seconds() // 60)
            hours_parked = round(duration_minutes / 60, 2)
            revenue = round(hours_parked * lot.price, 2) if lot else 0
        reservation_list.append({
            'lot_name': lot.prime_location_name if lot else '',
            'spot_number': spot.spot_number if spot else '',
            'date': r.parking_timestamp.strftime('%d-%b-%Y'),
            'time': r.parking_timestamp.strftime('%I:%M %p'),
            'hours_parked': hours_parked,
            'revenue': revenue,
            'status': r.status,
        })
    return render_template('user_history_modal.html', user=user, reservations=reservation_list)

@admin_bp.route('/admin/reservations')
@login_required
def reservation_list():
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    reservations = Reservation.query.order_by(Reservation.parking_timestamp.desc()).all()
    return render_template('reservation_list.html', reservations=reservations)

@admin_bp.route('/admin/reservations/delete/<int:reservation_id>', methods=['POST'])
@login_required
def delete_reservation(reservation_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    reservation = Reservation.query.get_or_404(reservation_id)
    db.session.delete(reservation)
    db.session.commit()
    return '', 204 

@admin_bp.route('/admin/users/details/<int:user_id>')
@login_required
def user_details(user_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    user = User.query.get_or_404(user_id)
    return render_template('user_details_modal.html', user=user) 

@admin_bp.route('/admin/fix_spot_occupancy/<int:lot_id>')
@login_required
def fix_spot_occupancy(lot_id):
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    fixed_count = 0
    for spot in spots:
        active_res = Reservation.query.filter_by(spot_id=spot.id, status='Active').first()
        if not active_res and spot.is_occupied:
            spot.is_occupied = False
            fixed_count += 1
    db.session.commit()
    flash(f'Fixed {fixed_count} stuck occupied spots in lot {lot.prime_location_name}.', 'success')
    return redirect(url_for('admin.lot_list')) 

@admin_bp.route('/admin/spot_reservation_details/<int:spot_id>')
@login_required
def spot_reservation_details(spot_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    from datetime import datetime
    from models.models import Reservation, ParkingSpot, User, ParkingLot
    spot = ParkingSpot.query.get(spot_id)
    if not spot:
        return jsonify({'success': False, 'error': 'Spot not found'})
    reservation = Reservation.query.filter_by(spot_id=spot_id).order_by(Reservation.parking_timestamp.desc()).first()
    if not reservation:
        return jsonify({'success': False, 'error': 'No reservation found for this spot.'})
    user = User.query.get(reservation.user_id)
    lot = ParkingLot.query.get(reservation.parking_lot_id)
    now = datetime.now()
    if reservation.leaving_timestamp:
        duration_minutes = int((reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() // 60)
    else:
        duration_minutes = int((now - reservation.parking_timestamp).total_seconds() // 60)
    hours_parked = round(duration_minutes / 60, 2)
    revenue = round(hours_parked * lot.price, 2) if lot else 0
    return jsonify({
        'success': True,
        'spot_id': spot_id,
        'spot_number': spot.spot_number,
        'user_id': user.id if user else '',
        'user_name': (user.first_name or '') + ' ' + (user.last_name or '') if user else '',
        'vehicle_number': reservation.vehicle_number,
        'phone_number': user.phone_number if user else '',
        'hours_parked': hours_parked,
        'revenue': revenue,
        'status': reservation.status,
        'reservation_id': reservation.id
    }) 

@admin_bp.route('/admin/spot_reservation_details/<int:lot_id>/<int:spot_number>')
@login_required
def spot_reservation_details_by_number(lot_id, spot_number):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    from datetime import datetime
    from models.models import Reservation, ParkingSpot, User, ParkingLot
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, spot_number=spot_number).first()
    if not spot:
        return jsonify({'success': False, 'error': 'Spot not found'})
    reservation = Reservation.query.filter_by(spot_id=spot.id).order_by(Reservation.parking_timestamp.desc()).first()
    if not reservation:
        return jsonify({'success': False, 'error': 'No reservation found for this spot.'})
    user = User.query.get(reservation.user_id)
    lot = ParkingLot.query.get(reservation.parking_lot_id)
    now = datetime.now()
    if reservation.leaving_timestamp:
        duration_minutes = int((reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() // 60)
    else:
        duration_minutes = int((now - reservation.parking_timestamp).total_seconds() // 60)
    hours_parked = round(duration_minutes / 60, 2)
    revenue = round(hours_parked * lot.price, 2) if lot else 0
    return jsonify({
        'success': True,
        'spot_id': spot.id,
        'spot_number': spot.spot_number,
        'user_id': user.id if user else '',
        'user_name': (user.first_name or '') + ' ' + (user.last_name or '') if user else '',
        'vehicle_number': reservation.vehicle_number,
        'phone_number': user.phone_number if user else '',
        'hours_parked': hours_parked,
        'revenue': revenue,
        'status': reservation.status,
        'reservation_id': reservation.id
    }) 

@admin_bp.route('/admin/summary')
@login_required
def summary():
    if not current_user.is_admin():
        return redirect(url_for('user.dashboard'))
    
    from models.models import ParkingLot, ParkingSpot, User, Reservation
    from datetime import datetime, timedelta
    
    # Total statistics
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    total_users = User.query.filter(User.role != 'admin').count()
    total_reservations = Reservation.query.count()
    
    # Occupied vs Available spots
    occupied_spots = ParkingSpot.query.filter_by(is_occupied=True).count()
    available_spots = total_spots - occupied_spots
    
    week_ago = datetime.now() - timedelta(days=7)
    recent_reservations = Reservation.query.filter(Reservation.parking_timestamp >= week_ago).count()
    
    # Revenue data (last 30 days)
    month_ago = datetime.now() - timedelta(days=30)
    monthly_reservations = Reservation.query.filter(
        Reservation.parking_timestamp >= month_ago,
        Reservation.leaving_timestamp.isnot(None)
    ).all()
    
    total_revenue = 0
    for res in monthly_reservations:
        if res.lot:
            duration = (res.leaving_timestamp - res.parking_timestamp).total_seconds() / 3600
            total_revenue += duration * res.lot.price
    
    # Top parking lots by usage
    lots_usage = []
    for lot in ParkingLot.query.all():
        lot_reservations = Reservation.query.filter_by(parking_lot_id=lot.id).count()
        lots_usage.append({
            'name': lot.prime_location_name,
            'usage': lot_reservations
        })
    lots_usage.sort(key=lambda x: x['usage'], reverse=True)
    top_lots = lots_usage[:5]
    
    return render_template('admin_summary.html', 
                         admin=current_user,
                         total_lots=total_lots,
                         total_spots=total_spots,
                         total_users=total_users,
                         total_reservations=total_reservations,
                         occupied_spots=occupied_spots,
                         available_spots=available_spots,
                         recent_reservations=recent_reservations,
                         total_revenue=round(total_revenue, 2),
                         top_lots=top_lots) 

@admin_bp.route('/admin/search/parking-lots')
@login_required
def search_parking_lots():
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    lots = ParkingLot.query.filter(
        db.or_(
            ParkingLot.prime_location_name.ilike(f'%{query}%'),
            ParkingLot.address.ilike(f'%{query}%'),
            ParkingLot.pin_code.ilike(f'%{query}%')
        )
    ).all()
    lots_data = []
    for lot in lots:
        occupied_count = ParkingSpot.query.filter_by(lot_id=lot.id, is_occupied=True).count()
        lots_data.append({
            'id': lot.id,
            'name': lot.prime_location_name,
            'address': lot.address,
            'pin_code': lot.pin_code,
            'total_spots': lot.number_of_spots,
            'occupied': occupied_count,
            'price_per_hour': lot.price
        })
    return jsonify(lots_data)

@admin_bp.route('/admin/search/parking-spots')
@login_required
def search_parking_spots():
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    query = request.args.get('q', '').strip().lower()
    status = request.args.get('status', '').strip().lower()
    # If query contains 'available' or 'occupied', set status
    if 'available' in query:
        status = 'available'
        query = query.replace('available', '').strip()
    elif 'occupied' in query:
        status = 'occupied'
        query = query.replace('occupied', '').strip()
    spots_query = ParkingSpot.query
    if status:
        if status == 'available':
            spots_query = spots_query.filter(ParkingSpot.is_occupied == False)
        elif status == 'occupied':
            spots_query = spots_query.filter(ParkingSpot.is_occupied == True)
    if query:
        spots_query = spots_query.join(ParkingLot).filter(
            db.or_(
                ParkingSpot.spot_number.ilike(f'%{query}%'),
                ParkingLot.prime_location_name.ilike(f'%{query}%'),
                ParkingLot.address.ilike(f'%{query}%')
            )
        )
    spots = spots_query.all()
    spots_data = []
    for spot in spots:
        lot = ParkingLot.query.get(spot.lot_id)
        spots_data.append({
            'id': spot.id,
            'spot_number': spot.spot_number,
            'status': spot.status,
            'is_occupied': spot.is_occupied,
            'floor': spot.floor,
            'lot_name': lot.prime_location_name if lot else 'Unknown',
            'lot_address': lot.address if lot else 'Unknown',
            'lot_id': spot.lot_id
        })
    return jsonify(spots_data) 

@admin_bp.route('/admin/search/users')
@login_required
def search_users():
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    search_type = request.args.get('type', 'Name')
    query = request.args.get('q', '').strip()
    min_res = request.args.get('min', type=int)
    max_res = request.args.get('max', type=int)
    users_query = User.query
    if search_type == 'Name':
        users_query = users_query.filter(
            db.or_(
                User.username.ilike(f'%{query}%'),
                User.first_name.ilike(f'%{query}%'),
                User.last_name.ilike(f'%{query}%')
            )
        )
    elif search_type == 'Address':
        users_query = users_query.filter(User.address.ilike(f'%{query}%'))
    elif search_type == 'Phone':
        users_query = users_query.filter(User.phone_number.ilike(f'%{query}%'))
    elif search_type == 'Age':
        if query.isdigit():
            users_query = users_query.filter(User.age == int(query))
        else:
            return jsonify([])
    elif search_type == 'Number of Reservations':
        pass
    users = users_query.all()
    
    # reservation count filter
    if search_type == 'Number of Reservations':
        user_ids = [u.id for u in users]
        res_counts = {u.id: Reservation.query.filter_by(user_id=u.id).count() for u in users}
        min_val = min_res if min_res is not None else 0
        max_val = max_res if max_res is not None else 50
        filtered = []
        for u in users:
            count = res_counts[u.id]
            if min_val <= count <= max_val:
                filtered.append(u)
        users = filtered
    result = []
    for user in users:
        res_count = Reservation.query.filter_by(user_id=user.id).count()
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'age': user.age,
            'phone_number': user.phone_number,
            'address': user.address,
            'reservations': res_count,
            'created_at': user.created_at.isoformat() if user.created_at else ''
        })
    return jsonify(result) 